"""
Auth views — ports the signup, customer login, and admin login flows.
Customer auth uses email/mobile; admin login restricts to ADMIN (scope=admin).
"""
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from .models import User, UserType, Status


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
            return redirect("/admin-panel")
        messages.error(request, "Invalid admin credentials.")
    return render(request, "registration/admin_login.html")


def logout_view(request):
    logout(request)
    return redirect("/")
