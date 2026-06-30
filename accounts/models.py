"""
Accounts models — port of the Prisma `User` and `UserAddress` models.
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserType(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    USER = "USER", "User"
    GUESTUSER = "GUESTUSER", "Guest User"


class Status(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


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
    reg_no = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    first_name = models.CharField(max_length=120, null=True, blank=True)
    last_name = models.CharField(max_length=120, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    mobile = models.CharField(max_length=20, unique=True, null=True, blank=True)
    user_image = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=120, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    user_type = models.CharField(max_length=10, choices=UserType.choices, default=UserType.USER)
    email_verify = models.BooleanField(default=True)
    last_login_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    # Map the domain user_type onto Django's staff/superuser flags so the
    # built-in admin and permission system "just work" for ADMIN users.
    @property
    def is_staff(self):
        return self.user_type == UserType.ADMIN

    @property
    def is_superuser(self):
        return self.user_type == UserType.ADMIN

    @is_superuser.setter
    def is_superuser(self, value):  # required by createsuperuser flow
        if value:
            self.user_type = UserType.ADMIN

    @is_staff.setter
    def is_staff(self, value):
        pass

    def has_perm(self, perm, obj=None):
        return self.user_type == UserType.ADMIN

    def has_module_perms(self, app_label):
        return self.user_type == UserType.ADMIN


class UserAddress(models.Model):
    user = models.ForeignKey(User, related_name="addresses", on_delete=models.CASCADE)
    address_name = models.CharField(max_length=120, null=True, blank=True)
    address = models.TextField()
    street_flat = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=120)
    pin_code = models.CharField(max_length=20)
    landmark = models.CharField(max_length=255, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_address"

    def __str__(self):
        return f"{self.address_name or 'Address'} — {self.city}"
