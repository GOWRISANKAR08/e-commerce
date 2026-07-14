"""
Auth views — ports the signup, customer login, and admin login flows.
Customer auth uses email/mobile; admin login restricts to ADMIN (scope=admin).
"""
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
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


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("/account")
    if request.method == "POST":
        first = request.POST.get("first_name", "").strip()
        last = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        mobile = request.POST.get("mobile", "").strip()
        password = request.POST.get("password", "")

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return render(request, "registration/signup.html", {"form": request.POST})
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, "registration/signup.html", {"form": request.POST})
        if mobile and User.objects.filter(mobile=mobile).exists():
            messages.error(request, "An account with this mobile already exists.")
            return render(request, "registration/signup.html", {"form": request.POST})

        user = User.objects.create_user(
            email=email, password=password, first_name=first, last_name=last,
            mobile=mobile or None, user_type=UserType.USER, status=Status.ACTIVE,
        )
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
