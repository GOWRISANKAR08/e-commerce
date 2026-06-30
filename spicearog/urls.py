from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts import views as auth_views
from store import views as site
from core import views as panel

admin.site.site_header = "Spicearog Administration"
admin.site.site_title = "Spicearog Admin"
admin.site.index_title = "Manage store data"

urlpatterns = [
    # ---- Auth ----
    path("login", auth_views.login_view, name="login"),
    path("signup", auth_views.signup_view, name="signup"),
    path("logout", auth_views.logout_view, name="logout"),
    path("admin-login", auth_views.admin_login_view, name="admin_login"),

    # ---- Custom admin panel (rich dashboard + CRUD) ----
    path("admin-panel", panel.dashboard, name="admin_dashboard"),
    path("admin-panel/products", panel.products_list, name="admin_products"),
    path("admin-panel/products/export", panel.product_export, name="admin_product_export"),
    path("admin-panel/products/new", panel.product_edit, name="admin_product_new"),
    path("admin-panel/products/<int:pk>/edit", panel.product_edit, name="admin_product_edit"),
    path("admin-panel/products/<int:pk>/clone", panel.product_clone, name="admin_product_clone"),
    path("admin-panel/products/<int:pk>/delete", panel.product_delete, name="admin_product_delete"),
    path("admin-panel/categories", panel.categories_list, name="admin_categories"),
    path("admin-panel/categories/export", panel.category_export, name="admin_category_export"),
    path("admin-panel/categories/<int:pk>/delete", panel.category_delete, name="admin_category_delete"),
    path("admin-panel/variants", panel.variants_list, name="admin_variants"),
    path("admin-panel/variants/<int:pk>/delete", panel.variant_delete, name="admin_variant_delete"),
    path("admin-panel/variants/<int:pk>/clone",  panel.variant_clone,  name="admin_variant_clone"),
    path("admin-panel/inventory", panel.inventory, name="admin_inventory"),
    path("admin-panel/orders", panel.orders_list, name="admin_orders"),
    path("admin-panel/orders/<int:pk>/update", panel.order_update, name="admin_order_update"),
    path("admin-panel/orders/<int:pk>/cancel", panel.order_cancel, name="admin_order_cancel"),
    path("admin-panel/orders/<int:pk>/refund", panel.order_refund, name="admin_order_refund"),
    path("admin-panel/users", panel.users_list, name="admin_users"),
    path("admin-panel/loyalty", panel.loyalty_members, name="admin_loyalty"),
    path("admin-panel/reports", panel.sales_reports, name="admin_reports"),
    path("admin-panel/revenue", panel.revenue_view, name="admin_revenue"),
    path("admin-panel/performance", panel.performance_view, name="admin_performance"),
    path("admin-panel/settings", panel.admin_settings, name="admin_settings"),
    path("admin-panel/integrations", panel.integrations_view, name="admin_integrations"),
    path("admin-panel/integrations/test/<str:integration>", panel.integration_test, name="admin_integration_test"),
    path("admin-panel/products/archived", panel.archived_products, name="admin_products_archived"),
    path("admin-panel/products/<int:pk>/restore", panel.product_restore, name="admin_product_restore"),
    path("admin-panel/products/import", panel.product_import, name="admin_product_import"),
    path("admin-panel/media/upload", panel.media_upload, name="admin_media_upload"),
    path("admin-panel/combos", panel.combo_list, name="admin_combos"),
    path("admin-panel/combos/new", panel.combo_edit, name="admin_combo_new"),
    path("admin-panel/combos/<int:pk>/edit", panel.combo_edit, name="admin_combo_edit"),
    path("admin-panel/combos/<int:pk>/delete", panel.combo_delete, name="admin_combo_delete"),
    path("admin-panel/combos/variants/search", panel.combo_variant_search, name="admin_combo_variant_search"),
    path("admin-panel/reviews", panel.reviews_list, name="admin_reviews"),
    path("admin-panel/reviews/export", panel.review_export, name="admin_review_export"),
    path("admin-panel/reviews/<int:pk>/reply", panel.review_reply, name="admin_review_reply"),
    path("admin-panel/reviews/<int:pk>/flag", panel.review_flag, name="admin_review_flag"),
    path("admin-panel/reviews/<int:pk>/delete", panel.review_delete, name="admin_review_delete"),
    path("admin-panel/banners", panel.banners_list, name="admin_banners"),
    path("admin-panel/banners/new", panel.banner_edit, name="admin_banner_new"),
    path("admin-panel/banners/<int:pk>/edit", panel.banner_edit, name="admin_banner_edit"),
    path("admin-panel/banners/<int:pk>/delete", panel.banner_delete, name="admin_banner_delete"),
    path("admin-panel/banners/<int:pk>/toggle", panel.banner_toggle, name="admin_banner_toggle"),
    path("admin-panel/coupons", panel.coupons_list, name="admin_coupons"),
    path("admin-panel/coupons/new", panel.coupon_edit, name="admin_coupon_new"),
    path("admin-panel/coupons/<int:pk>/edit", panel.coupon_edit, name="admin_coupon_edit"),
    path("admin-panel/coupons/<int:pk>/delete", panel.coupon_delete, name="admin_coupon_delete"),
    path("admin-panel/coupons/<int:pk>/toggle", panel.coupon_toggle, name="admin_coupon_toggle"),

    # ---- Django admin (manages long-tail content models) ----
    path("admin/", admin.site.urls),

    # ---- Storefront APIs / actions ----
    path("api/cart/add", site.cart_add, name="cart_add"),
    path("api/cart/remove", site.cart_remove, name="cart_remove"),
    path("api/favourites/toggle", site.favourite_toggle, name="favourite_toggle"),
    path("api/reviews", site.review_create, name="review_create"),

    # ---- Storefront pages ----
    path("", site.home, name="home"),
    path("products", site.products, name="products"),
    path("categories", site.categories, name="categories"),
    path("product/<slug:slug>", site.product_detail, name="product_detail"),
    path("cart", site.cart_view, name="cart"),
    path("favourites", site.favourites, name="favourites"),
    path("orders", site.orders, name="orders"),
    path("checkout", site.checkout, name="checkout"),
    path("account", site.account, name="account"),
    path("notifications", site.notifications, name="notifications"),
    path("blogs", site.blogs, name="blogs"),
    path("blogs/<slug:slug>", site.blog_detail, name="blog_detail"),
    path("faq", site.faq, name="faq"),
    path("testimonials", site.testimonials, name="testimonials"),
    path("about-us", site.about, name="about"),
    path("terms", site.terms, name="terms"),
    path("privacy-policy", site.privacy, name="privacy"),
    path("help-support", site.help_support, name="help_support"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    # Seed placeholder imagery is stored at static/seed/ but referenced by the
    # original app's absolute "/seed/..." paths, so map that prefix too.
    urlpatterns += static("/seed/", document_root=settings.STATICFILES_DIRS[0] / "seed")
