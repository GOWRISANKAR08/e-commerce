"""
Authentication backend — port of the NextAuth Credentials `authorize` logic.

Logs in by email OR mobile, blocks INACTIVE users, and supports an "admin"
scope that only permits ADMIN users (used by the admin login screen).
"""
from django.contrib.auth.backends import BaseBackend
from django.utils import timezone

from .models import User, Status, UserType


class EmailOrMobileBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, scope=None, **kwargs):
        identifier = (username or kwargs.get("email") or "").strip()
        if not identifier or not password:
            return None
        user = (
            User.objects.filter(email__iexact=identifier).first()
            or User.objects.filter(mobile=identifier).first()
        )
        if user is None or not user.password:
            return None
        if user.status != Status.ACTIVE:
            return None
        if not user.check_password(password):
            return None
        # Admin login screen must only accept ADMIN users
        if scope == "admin" and user.user_type != UserType.ADMIN:
            return None
        user.last_login_date = timezone.now()
        user.save(update_fields=["last_login_date"])
        return user

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id).first()
