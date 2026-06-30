from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserAddress


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("email", "mobile", "full_name", "user_type", "status", "created_at")
    list_filter = ("user_type", "status")
    search_fields = ("email", "mobile", "first_name", "last_name")
    readonly_fields = ("reg_no", "created_at", "updated_at", "last_login_date")
    fieldsets = (
        (None, {"fields": ("email", "mobile", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "city", "user_image")}),
        ("Status", {"fields": ("user_type", "status", "email_verify")}),
        ("Meta", {"fields": ("reg_no", "last_login_date", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "mobile", "password1", "password2", "user_type", "status")}),
    )
    filter_horizontal = ()


admin.site.register(UserAddress)
