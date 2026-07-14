"""
Accounts models — port of the Prisma `User` and `UserAddress` models,
extended with profile management, login history, OTP verification, and activity logging.
"""
import uuid
import random
import string
from datetime import timedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserType(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    USER = "USER", "User"
    GUESTUSER = "GUESTUSER", "Guest User"


class Status(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class Gender(models.TextChoices):
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"
    OTHER = "OTHER", "Other"
    PREFER_NOT = "PREFER_NOT", "Prefer not to say"


class AddressType(models.TextChoices):
    HOME = "HOME", "Home"
    OFFICE = "OFFICE", "Office"
    OTHER = "OTHER", "Other"


class OTPType(models.TextChoices):
    EMAIL_CHANGE = "EMAIL_CHANGE", "Email Change"
    PHONE_CHANGE = "PHONE_CHANGE", "Phone Change"
    DELETE_ACCOUNT = "DELETE_ACCOUNT", "Delete Account"


class ActivityType(models.TextChoices):
    ORDER_PLACED = "ORDER_PLACED", "Order Placed"
    PROFILE_UPDATED = "PROFILE_UPDATED", "Profile Updated"
    PHOTO_UPDATED = "PHOTO_UPDATED", "Photo Updated"
    EMAIL_CHANGED = "EMAIL_CHANGED", "Email Changed"
    PHONE_CHANGED = "PHONE_CHANGED", "Phone Changed"
    PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password Changed"
    ADDRESS_ADDED = "ADDRESS_ADDED", "Address Added"
    ADDRESS_UPDATED = "ADDRESS_UPDATED", "Address Updated"
    ADDRESS_DELETED = "ADDRESS_DELETED", "Address Deleted"
    REVIEW_SUBMITTED = "REVIEW_SUBMITTED", "Review Submitted"
    LOGIN = "LOGIN", "Logged In"
    LOGOUT = "LOGOUT", "Logged Out"
    WISHLIST_UPDATED = "WISHLIST_UPDATED", "Wishlist Updated"
    NOTIF_PREFS = "NOTIF_PREFS", "Notification Preferences Updated"


class UserManager(BaseUserManager):
    """Authenticate primarily by email; allow mobile-only accounts too."""

    def _create(self, email=None, password=None, **extra):
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra):
        extra.setdefault("user_type", UserType.USER)
        return self._create(email, password, **extra)

    def create_superuser(self, email=None, password=None, **extra):
        extra["user_type"] = UserType.ADMIN
        extra["status"] = Status.ACTIVE
        extra["email_verify"] = True
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    reg_no         = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    first_name     = models.CharField(max_length=120, null=True, blank=True)
    last_name      = models.CharField(max_length=120, null=True, blank=True)
    email          = models.EmailField(unique=True, null=True, blank=True)
    mobile         = models.CharField(max_length=20, unique=True, null=True, blank=True)
    user_image     = models.CharField(max_length=255, null=True, blank=True)
    city           = models.CharField(max_length=120, null=True, blank=True)
    status         = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    user_type      = models.CharField(max_length=10, choices=UserType.choices, default=UserType.USER)
    email_verify   = models.BooleanField(default=True)
    manual_tags    = models.CharField(max_length=200, blank=True, default="")
    last_login_date = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    # ── Extended profile fields ──────────────────────────────────────────────
    date_of_birth    = models.DateField(null=True, blank=True)
    gender           = models.CharField(max_length=10, choices=Gender.choices, null=True, blank=True)
    profile_image_url = models.CharField(max_length=500, null=True, blank=True)
    loyalty_points   = models.IntegerField(default=0)
    wallet_balance   = models.FloatField(default=0.0)

    # ── Notification preferences ─────────────────────────────────────────────
    notif_email = models.BooleanField(default=True)
    notif_sms   = models.BooleanField(default=True)
    notif_push  = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.full_name or self.email or self.mobile or f"user#{self.pk}"

    @property
    def full_name(self):
        return " ".join(p for p in [self.first_name, self.last_name] if p).strip()

    @property
    def display_image(self):
        """Return profile_image_url if set, else legacy user_image."""
        return self.profile_image_url or self.user_image or ""

    # Map the domain user_type onto Django's staff/superuser flags so the
    # built-in admin and permission system "just work" for ADMIN users.
    @property
    def is_staff(self):
        return self.user_type == UserType.ADMIN

    @property
    def is_superuser(self):
        return self.user_type == UserType.ADMIN

    @is_superuser.setter
    def is_superuser(self, value):
        if value:
            self.user_type = UserType.ADMIN

    @is_staff.setter
    def is_staff(self, value):
        pass

    def has_perm(self, perm, obj=None):
        return self.user_type == UserType.ADMIN

    def has_module_perms(self, app_label):
        return self.user_type == UserType.ADMIN


class CustomerNote(models.Model):
    user     = models.ForeignKey(User, related_name="customer_notes", on_delete=models.CASCADE)
    note     = models.TextField()
    author   = models.ForeignKey(User, null=True, blank=True,
                                 related_name="authored_notes", on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer_notes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note on {self.user} by {self.author}"


class UserAddress(models.Model):
    user           = models.ForeignKey(User, related_name="addresses", on_delete=models.CASCADE)
    address_name   = models.CharField(max_length=120, null=True, blank=True)
    address_type   = models.CharField(max_length=10, choices=AddressType.choices, default=AddressType.HOME)
    recipient_name = models.CharField(max_length=150, null=True, blank=True)
    phone          = models.CharField(max_length=20, null=True, blank=True)
    address        = models.TextField()
    street_flat    = models.CharField(max_length=255, null=True, blank=True)
    landmark       = models.CharField(max_length=255, null=True, blank=True)
    city           = models.CharField(max_length=120)
    state          = models.CharField(max_length=120, null=True, blank=True)
    pin_code       = models.CharField(max_length=20)
    is_default     = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_address"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.get_address_type_display()} — {self.city}"


class LoginHistory(models.Model):
    class LoginStatus(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    user       = models.ForeignKey(User, related_name="login_history", on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default="")
    device     = models.CharField(max_length=200, blank=True, default="")
    status     = models.CharField(max_length=10, choices=LoginStatus.choices, default=LoginStatus.SUCCESS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "login_history"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.status} @ {self.created_at:%Y-%m-%d %H:%M}"


class OTPRequest(models.Model):
    user       = models.ForeignKey(User, related_name="otp_requests", on_delete=models.CASCADE)
    otp_type   = models.CharField(max_length=20, choices=OTPType.choices)
    new_value  = models.CharField(max_length=255, blank=True, default="")
    code       = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "otp_requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.otp_type} OTP for {self.user}"

    @classmethod
    def create_for(cls, user, otp_type, new_value="", ttl_minutes=10):
        code = "".join(random.choices(string.digits, k=6))
        cls.objects.filter(user=user, otp_type=otp_type, is_used=False).update(is_used=True)
        return cls.objects.create(
            user=user,
            otp_type=otp_type,
            new_value=new_value,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()


class ActivityLog(models.Model):
    user        = models.ForeignKey(User, related_name="activity_logs", on_delete=models.CASCADE)
    action_type = models.CharField(max_length=30, choices=ActivityType.choices)
    description = models.CharField(max_length=500, blank=True, default="")
    metadata    = models.CharField(max_length=500, blank=True, default="")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activity_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action_type} by {self.user} at {self.created_at:%Y-%m-%d %H:%M}"

    @classmethod
    def log(cls, user, action_type, description="", metadata=""):
        cls.objects.create(user=user, action_type=action_type,
                           description=description, metadata=metadata)
