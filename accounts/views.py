"""
Auth views — ports the signup, customer login, and admin login flows.
Customer auth uses email/mobile; admin login restricts to ADMIN (scope=admin).
"""
import json
import re
import random
import string
import time

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .models import User, UserType, Status


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _record_login(user, request, status="SUCCESS"):
    try:
        from accounts.models import LoginHistory, ActivityLog, ActivityType
        ua = request.META.get("HTTP_USER_AGENT", "")[:500]
        ua_lower = ua.lower()
        if any(k in ua_lower for k in ("mobile", "android", "iphone")):
            device = "Mobile"
        elif any(k in ua_lower for k in ("tablet", "ipad")):
            device = "Tablet"
        else:
            device = "Desktop"
        LoginHistory.objects.create(
            user=user,
            ip_address=_get_client_ip(request),
            user_agent=ua,
            device=device,
            status=status,
        )
        if status == "SUCCESS":
            ActivityLog.log(user, ActivityType.LOGIN,
                            f"Logged in from {device}")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Registration email OTP helpers
# --------------------------------------------------------------------------- #

def _send_signup_otp(email, code):
    """Send registration OTP via configured SMTP. Returns (sent: bool, err: str|None)."""
    from store.models import IntegrationConfig
    host     = IntegrationConfig.get("EMAIL", "host", "")
    port     = int(IntegrationConfig.get("EMAIL", "port", "587") or 587)
    username = IntegrationConfig.get("EMAIL", "username", "")
    password = IntegrationConfig.get("EMAIL", "password", "")
    use_tls  = IntegrationConfig.get("EMAIL", "use_tls", "true") == "true"
    from_em  = IntegrationConfig.get("EMAIL", "from_email", "") or username
    enabled  = IntegrationConfig.get("EMAIL", "enabled", "false") == "true"

    if not enabled or not host or not username:
        return False, "not_configured"

    from django.core.mail import get_connection, EmailMultiAlternatives
    conn = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=host, port=port, username=username, password=password,
        use_tls=use_tls, fail_silently=False,
    )
    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;">
      <h2 style="color:#1b2420;font-size:20px;margin:0 0 8px;">Verify your email</h2>
      <p style="color:#666;margin:0 0 24px;font-size:14px;">
        Enter this code to complete your Spicearog account registration.<br>It expires in 10&nbsp;minutes.
      </p>
      <div style="background:#eef6ef;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px;">
        <span style="font-size:38px;font-weight:700;letter-spacing:10px;color:#1f6b3a;">{code}</span>
      </div>
      <p style="color:#999;font-size:12px;margin:0;">If you didn't request this, you can safely ignore this email.</p>
    </div>"""
    try:
        msg = EmailMultiAlternatives(
            "Verify your email — Spicearog",
            f"Your verification code: {code}",
            from_em,
            [email],
            connection=conn,
        )
        msg.attach_alternative(html, "text/html")
        msg.send()
        return True, None
    except Exception as exc:
        return False, str(exc)


def _send_signup_mobile_otp(full_phone, code):
    """Send OTP via configured SMS provider. Returns (sent: bool, err: str|None)."""
    from store.models import IntegrationConfig
    provider = IntegrationConfig.get("SMS", "provider", "").lower()
    api_key  = IntegrationConfig.get("SMS", "api_key", "")
    sender   = IntegrationConfig.get("SMS", "sender_id", "")
    enabled  = IntegrationConfig.get("SMS", "enabled", "false") == "true"

    if not enabled or not provider or not api_key:
        return False, "not_configured"

    digits_only = full_phone.lstrip("+").replace(" ", "").replace("-", "")
    msg = f"Your Spicearog verification code: {code}. Valid for 10 minutes. Do not share this code."

    try:
        import urllib.request as _ur
        import urllib.parse as _up

        if provider == "fast2sms":
            params = _up.urlencode({"route": "q", "message": msg, "numbers": digits_only, "flash": 0})
            req = _ur.Request(
                f"https://www.fast2sms.com/dev/bulkV2?{params}",
                headers={"authorization": api_key},
            )
            with _ur.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            return (True, None) if data.get("return") else (False, str(data.get("message", "Send failed")))

        elif provider == "msg91":
            payload = json.dumps({
                "mobile": digits_only, "authkey": api_key, "otp": code,
                "sender": sender or "SPICE", "otp_expiry": 10,
            }).encode()
            req = _ur.Request(
                "https://api.msg91.com/api/v5/otp", data=payload, method="POST",
                headers={"authkey": api_key, "content-type": "application/json"},
            )
            with _ur.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            return (True, None) if data.get("type") == "success" else (False, str(data.get("message", "Send failed")))

        elif provider == "twilio":
            account_sid = IntegrationConfig.get("SMS", "account_sid", "")
            if not account_sid:
                return False, "Twilio Account SID not configured."
            import base64
            payload = _up.urlencode({"To": full_phone, "From": sender, "Body": msg}).encode()
            req = _ur.Request(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                data=payload, method="POST",
            )
            req.add_header("Authorization", "Basic " + base64.b64encode(f"{account_sid}:{api_key}".encode()).decode())
            with _ur.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            status = data.get("status", "")
            return (True, None) if status in ("queued", "sent", "delivered") else (False, str(data.get("message", status)))

        else:
            return False, f"Unknown SMS provider: {provider}"

    except Exception as exc:
        return False, str(exc)


def signup_mobile_otp_send(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid request."})

    try:
        country_code = data.get("country_code", "").strip()
        mobile       = data.get("mobile", "").strip()

        if not country_code:
            return JsonResponse({"ok": False, "error": "Please select a country code."})
        if not mobile:
            return JsonResponse({"ok": False, "error": "Mobile number is required."})
        if not re.match(r"^\d{5,15}$", mobile):
            return JsonResponse({"ok": False, "error": "Enter a valid mobile number (digits only)."})
        if User.objects.filter(mobile=mobile).exists():
            return JsonResponse({"ok": False, "error": "An account with this mobile number already exists."})

        full_phone = country_code + mobile
        code = "".join(random.choices(string.digits, k=6))
        request.session["signup_mobile_otp"] = {
            "phone": full_phone,
            "code": code,
            "expires_at": time.time() + 600,
        }
        request.session.modified = True

        sent, err = _send_signup_mobile_otp(full_phone, code)
        if not sent:
            if err == "not_configured":
                return JsonResponse({"ok": False, "error": "SMS delivery is not configured. Please contact support."})
            return JsonResponse({"ok": False, "error": "Failed to send SMS. Please try again."})

        return JsonResponse({"ok": True, "message": f"OTP sent to {full_phone}"})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("signup_mobile_otp_send error")
        from django.conf import settings as dj_settings
        detail = f": {exc}" if dj_settings.DEBUG else ""
        return JsonResponse({"ok": False, "error": f"Server error{detail}. Please try again."})


def signup_mobile_otp_verify(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid request."})

    try:
        country_code = data.get("country_code", "").strip()
        mobile       = data.get("mobile", "").strip()
        code         = data.get("code", "").strip()
        full_phone   = country_code + mobile

        otp_data = request.session.get("signup_mobile_otp")
        if not otp_data:
            return JsonResponse({"ok": False, "error": "No OTP was requested. Please send a verification code first."})
        if otp_data.get("phone") != full_phone:
            return JsonResponse({"ok": False, "error": "OTP was sent to a different number."})
        if time.time() > otp_data.get("expires_at", 0):
            request.session.pop("signup_mobile_otp", None)
            return JsonResponse({"ok": False, "error": "OTP has expired. Please request a new one."})
        if otp_data.get("code") != code:
            return JsonResponse({"ok": False, "error": "Incorrect OTP. Please check and try again."})

        request.session["signup_mobile_verified"] = full_phone
        request.session.pop("signup_mobile_otp", None)
        request.session.modified = True
        return JsonResponse({"ok": True, "message": "Mobile number verified successfully!"})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("signup_mobile_otp_verify error")
        from django.conf import settings as dj_settings
        detail = f": {exc}" if dj_settings.DEBUG else ""
        return JsonResponse({"ok": False, "error": f"Server error{detail}. Please try again."})


def signup_email_otp_send(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid request."})

    try:
        email = data.get("email", "").strip().lower()
        if not email:
            return JsonResponse({"ok": False, "error": "Email is required."})
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return JsonResponse({"ok": False, "error": "Enter a valid email address."})
        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({"ok": False, "error": "An account with this email already exists."})

        code = "".join(random.choices(string.digits, k=6))
        request.session["signup_otp"] = {
            "email": email,
            "code": code,
            "expires_at": time.time() + 600,
        }
        request.session.modified = True

        sent, err = _send_signup_otp(email, code)
        if not sent:
            if err == "not_configured":
                return JsonResponse({"ok": False, "error": "Email delivery is not configured. Please contact support."})
            return JsonResponse({"ok": False, "error": "Failed to send verification email. Please try again."})

        return JsonResponse({"ok": True, "message": f"Verification code sent to {email}"})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("signup_email_otp_send error")
        from django.conf import settings as dj_settings
        detail = f": {exc}" if dj_settings.DEBUG else ""
        return JsonResponse({"ok": False, "error": f"Server error{detail}. Please try again."})


def signup_email_otp_verify(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid request."})

    try:
        email = data.get("email", "").strip().lower()
        code  = data.get("code", "").strip()

        otp_data = request.session.get("signup_otp")
        if not otp_data:
            return JsonResponse({"ok": False, "error": "No OTP was requested. Please send a verification code first."})
        if otp_data.get("email") != email:
            return JsonResponse({"ok": False, "error": "OTP was sent to a different email address."})
        if time.time() > otp_data.get("expires_at", 0):
            request.session.pop("signup_otp", None)
            return JsonResponse({"ok": False, "error": "OTP has expired. Please request a new one."})
        if otp_data.get("code") != code:
            return JsonResponse({"ok": False, "error": "Incorrect OTP. Please check and try again."})

        request.session["signup_email_verified"] = email
        request.session.pop("signup_otp", None)
        request.session.modified = True
        return JsonResponse({"ok": True, "message": "Email verified successfully!"})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("signup_email_otp_verify error")
        from django.conf import settings as dj_settings
        detail = f": {exc}" if dj_settings.DEBUG else ""
        return JsonResponse({"ok": False, "error": f"Server error{detail}. Please try again."})


# --------------------------------------------------------------------------- #
# Auth views
# --------------------------------------------------------------------------- #

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("/account")
    if request.method == "POST":
        first        = request.POST.get("first_name", "").strip()
        last         = request.POST.get("last_name", "").strip()
        email        = request.POST.get("email", "").strip().lower()
        mobile       = request.POST.get("mobile", "").strip()
        country_code = request.POST.get("country_code", "").strip()
        password     = request.POST.get("password", "")

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return render(request, "registration/signup.html", {"form": request.POST})
        if not mobile:
            messages.error(request, "Mobile number is required.")
            return render(request, "registration/signup.html", {"form": request.POST})

        if request.session.get("signup_email_verified", "").lower() != email:
            messages.error(request, "Please verify your email address before creating an account.")
            return render(request, "registration/signup.html", {"form": request.POST, "needs_verify": True})

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, "registration/signup.html", {"form": request.POST})
        if User.objects.filter(mobile=mobile).exists():
            messages.error(request, "An account with this mobile number already exists.")
            return render(request, "registration/signup.html", {"form": request.POST})

        user = User.objects.create_user(
            email=email, password=password, first_name=first, last_name=last,
            mobile=mobile, country_code=country_code or None,
            user_type=UserType.USER, status=Status.ACTIVE,
        )
        request.session.pop("signup_email_verified", None)
        login(request, user, backend="accounts.backends.EmailOrMobileBackend")
        _record_login(user, request)
        messages.success(request, "Welcome to Spicearog!")
        return redirect("/account")
    return render(request, "registration/signup.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/account")
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=identifier, password=password)
        if user:
            login(request, user, backend="accounts.backends.EmailOrMobileBackend")
            from django.utils import timezone
            user.last_login_date = timezone.now()
            user.save(update_fields=["last_login_date"])
            _record_login(user, request)
            nxt = request.GET.get("next") or "/account"
            return redirect(nxt)
        messages.error(request, "Invalid credentials or inactive account.")
    return render(request, "registration/login.html")


def admin_login_view(request):
    if request.user.is_authenticated and request.user.user_type == UserType.ADMIN:
        return redirect("/admin-panel")
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=identifier, password=password, scope="admin")
        if user:
            login(request, user, backend="accounts.backends.EmailOrMobileBackend")
            _record_login(user, request)
            return redirect("/admin-panel")
        messages.error(request, "Invalid admin credentials.")
    return render(request, "registration/admin_login.html")


def logout_view(request):
    if request.user.is_authenticated:
        try:
            from accounts.models import ActivityLog, ActivityType
            ActivityLog.log(request.user, ActivityType.LOGOUT, "Logged out")
        except Exception:
            pass
    logout(request)
    return redirect("/")
