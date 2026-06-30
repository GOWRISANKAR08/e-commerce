from django.contrib import admin

from .models import (
    Banner, Blog, Cart, CartItem, Category, Enquiry, Favourite, Faq, HomeOffer,
    Notification, Order, OrderItem, ParentCategory, Policy, Product,
    ProductImage, ProductVariant, Review, Testimonial,
)


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "is_featured", "top_seller", "badge", "status", "position")
    list_filter = ("status", "is_featured", "top_seller", "category")
    search_fields = ("name", "code", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [VariantInline, ImageInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent", "position", "status", "coming_soon")
    list_filter = ("status",)
    search_fields = ("name", "code", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductVariant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("va_code", "product", "variant", "selling_price", "mrp_price", "stock", "stock_status", "status")
    list_filter = ("stock_status", "status")
    search_fields = ("va_code", "product__name")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_id", "user", "grand_total", "status", "payment_status", "payment_mode", "created_at")
    list_filter = ("status", "payment_status", "payment_mode")
    search_fields = ("order_id", "invoice_no", "user__email")
    inlines = [OrderItemInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "status", "created_at")
    list_filter = ("status", "rating")


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "email", "subject")


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "position", "status")
    list_filter = ("type", "status")


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ("title", "tag", "status", "created_at")
    list_filter = ("status",)
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title",)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "rating", "position", "status")
    list_filter = ("status",)


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ("question", "position", "status")
    list_filter = ("status",)


@admin.register(HomeOffer)
class HomeOfferAdmin(admin.ModelAdmin):
    list_display = ("offer_name", "to_date", "position", "status")
    list_filter = ("status",)


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "updated_at")


admin.site.register(ParentCategory)
admin.site.register(Favourite)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Notification)
