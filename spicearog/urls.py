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
    path("api/signup/email-otp-send",    auth_views.signup_email_otp_send,    name="signup_email_otp_send"),
    path("api/signup/email-otp-verify",  auth_views.signup_email_otp_verify,  name="signup_email_otp_verify"),
    path("api/signup/mobile-otp-send",   auth_views.signup_mobile_otp_send,   name="signup_mobile_otp_send"),
    path("api/signup/mobile-otp-verify", auth_views.signup_mobile_otp_verify, name="signup_mobile_otp_verify"),

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
    path("admin-panel/variants/next-position",    panel.variant_next_position, name="variant_next_position"),
    path("admin-panel/variants/<int:pk>/edit",   panel.variant_edit,   name="admin_variant_edit"),
    path("admin-panel/variants/<int:pk>/delete", panel.variant_delete, name="admin_variant_delete"),
    path("admin-panel/variants/<int:pk>/clone",  panel.variant_clone,  name="admin_variant_clone"),
    path("admin-panel/inventory", panel.inventory, name="admin_inventory"),
    path("admin-panel/orders", panel.orders_list, name="admin_orders"),
    path("admin-panel/orders/<int:pk>", panel.order_detail, name="admin_order_detail"),
    path("admin-panel/orders/<int:pk>/update", panel.order_update, name="admin_order_update"),
    path("admin-panel/orders/<int:pk>/cancel", panel.order_cancel, name="admin_order_cancel"),
    path("admin-panel/orders/<int:pk>/refund", panel.order_refund, name="admin_order_refund"),
    path("admin-panel/orders/<int:pk>/note", panel.order_note_add, name="admin_order_note"),
    path("admin-panel/users", panel.users_list, name="admin_users"),
    path("admin-panel/users/export", panel.user_export, name="admin_user_export"),
    path("admin-panel/users/<int:pk>", panel.user_detail, name="admin_user_detail"),
    path("admin-panel/users/<int:pk>/toggle", panel.user_toggle_status, name="admin_user_toggle"),
    path("admin-panel/loyalty", panel.loyalty_members, name="admin_loyalty"),
    path("admin-panel/reports", panel.sales_reports, name="admin_reports"),
    path("admin-panel/revenue", panel.revenue_view, name="admin_revenue"),
    path("admin-panel/performance", panel.performance_view, name="admin_performance"),
    path("admin-panel/marketing/newsletter", panel.newsletter_view, name="admin_newsletter"),
    path("admin-panel/settings", panel.admin_settings, name="admin_settings"),
    path("admin-panel/settings/test/<str:integration>", panel.integration_test, name="admin_settings_test"),
    # ── CMS ──
    path("admin-panel/cms",                                panel.cms_dashboard,        name="cms_dashboard"),
    path("admin-panel/cms/page/<str:page_type>",           panel.cms_page_edit,        name="cms_page_edit"),
    path("admin-panel/cms/revisions/<int:pk>/restore",     panel.cms_revision_restore, name="cms_revision_restore"),
    path("admin-panel/cms/faq",                            panel.cms_faq,              name="cms_faq"),
    path("admin-panel/cms/faq/reorder",                    panel.cms_faq_reorder,      name="cms_faq_reorder"),
    path("admin-panel/cms/about",                          panel.cms_about,            name="cms_about"),
    path("admin-panel/cms/about/team/reorder",             panel.cms_team_reorder,     name="cms_team_reorder"),
    path("admin-panel/cms/enquiries",                      panel.cms_enquiries,        name="cms_enquiries"),
    path("admin-panel/cms/enquiries/<int:pk>",             panel.cms_enquiry_detail,   name="cms_enquiry_detail"),
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
    path("admin-panel/reviews/<int:pk>/approve", panel.review_approve, name="admin_review_approve"),
    path("admin-panel/reviews/<int:pk>/reject", panel.review_reject, name="admin_review_reject"),
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
    path("admin-panel/coupons/<int:pk>", panel.coupon_detail, name="admin_coupon_detail"),
    path("admin-panel/coupons/<int:pk>/edit", panel.coupon_edit, name="admin_coupon_edit"),
    path("admin-panel/coupons/<int:pk>/delete", panel.coupon_delete, name="admin_coupon_delete"),
    path("admin-panel/coupons/<int:pk>/toggle", panel.coupon_toggle, name="admin_coupon_toggle"),
    path("admin-panel/coupons/<int:pk>/duplicate", panel.coupon_duplicate, name="admin_coupon_duplicate"),

    # ---- Django admin (manages long-tail content models) ----
    path("admin/", admin.site.urls),

    # ---- Storefront APIs / actions ----
    path("api/cart/add", site.cart_add, name="cart_add"),
    path("api/cart/remove", site.cart_remove, name="cart_remove"),
    path("api/favourites/toggle", site.favourite_toggle, name="favourite_toggle"),
    path("api/reviews", site.review_create, name="review_create"),
    path("api/reviews/<int:pk>/edit", site.review_edit, name="review_edit"),
    path("api/reviews/<int:pk>/delete", site.review_delete_customer, name="review_delete_customer"),
    path("api/coupon/validate", panel.coupon_validate_api, name="coupon_validate"),
    path("api/coupon/apply", site.coupon_apply, name="coupon_apply"),
    path("api/coupon/remove", site.coupon_remove, name="coupon_remove"),
    path("api/product/<slug:slug>/quick-view", site.product_quick_view, name="product_quick_view"),
    path("api/address/<int:pk>/update", site.address_update, name="address_update"),
    path("api/combo/add", site.combo_cart_add, name="combo_cart_add"),
    path("api/combo/<slug:slug>/remove", site.combo_cart_remove, name="combo_cart_remove"),

    # ---- Storefront pages ----
    path("", site.home, name="home"),
    path("products", site.products, name="products"),
    path("combos", site.combo_list, name="combo_list"),
    path("combo/<slug:slug>", site.combo_detail, name="combo_detail"),
    path("categories", site.categories, name="categories"),
    path("product/<slug:slug>", site.product_detail, name="product_detail"),
    path("cart", site.cart_view, name="cart"),
    path("favourites", site.favourites, name="favourites"),
    path("orders", site.orders, name="orders"),
    path("orders/<str:order_id>", site.order_detail_customer, name="order_detail_customer"),
    path("orders/<str:order_id>/cancel", site.order_cancel_customer, name="order_cancel_customer"),
    path("orders/<str:order_id>/reorder", site.order_reorder, name="order_reorder"),
    path("orders/<str:order_id>/invoice", site.order_invoice_customer, name="order_invoice_customer"),
    path("checkout", site.checkout, name="checkout"),
    path("checkout/verify-payment", site.razorpay_verify, name="razorpay_verify"),
    path("checkout/payment-failed", site.razorpay_payment_failed, name="razorpay_payment_failed"),
    path("webhook/razorpay", site.razorpay_webhook, name="razorpay_webhook"),
    path("account", site.account, name="account"),

    # ── Profile management APIs ──
    path("api/profile/update",              site.profile_update,           name="profile_update"),
    path("api/profile/photo",               site.profile_photo_upload,     name="profile_photo_upload"),
    path("api/profile/email-change",        site.email_change_request,     name="email_change_request"),
    path("api/profile/email-verify",        site.email_change_verify,      name="email_change_verify"),
    path("api/profile/phone-change",        site.phone_change_request,     name="phone_change_request"),
    path("api/profile/phone-verify",        site.phone_change_verify,      name="phone_change_verify"),
    path("api/profile/password",            site.password_change_view,     name="password_change"),
    path("api/profile/notif-prefs",         site.notification_prefs_update, name="notif_prefs_update"),
    path("api/profile/logout-all",          site.logout_all_sessions,      name="logout_all_sessions"),
    path("api/profile/delete-request",      site.delete_account_request,   name="delete_account_request"),
    path("api/profile/delete-confirm",      site.delete_account_confirm,   name="delete_account_confirm"),

    # ── Address management APIs ──
    path("api/address/add",                 site.address_add,              name="address_add"),
    path("api/address/<int:pk>/edit",       site.address_edit,             name="address_edit"),
    path("api/address/<int:pk>/delete",     site.address_delete,           name="address_delete"),
    path("api/address/<int:pk>/default",    site.address_set_default,      name="address_set_default"),

    path("notifications", site.notifications, name="notifications"),
    path("my-reviews", site.my_reviews, name="my_reviews"),
    path("faq", site.faq, name="faq"),
    path("shipping-policy", site.shipping_policy, name="shipping_policy"),
    path("returns", site.returns_policy, name="returns_policy"),
    path("testimonials", site.testimonials, name="testimonials"),
    path("submit-testimonial", site.submit_testimonial, name="submit_testimonial"),
    path("testimonial/<int:pk>/delete", site.delete_testimonial, name="delete_testimonial"),
    path("about-us", site.about, name="about"),
    path("terms", site.terms, name="terms"),
    path("privacy-policy", site.privacy, name="privacy"),
    path("help-support", site.help_support, name="help_support"),
    # ── Admin testimonials ──
    path("admin-panel/testimonials",                    panel.testimonials_admin,       name="admin_testimonials"),
    path("admin-panel/testimonials/<int:pk>/approve",   panel.testimonial_approve,      name="testimonial_approve"),
    path("admin-panel/testimonials/<int:pk>/reject",    panel.testimonial_reject,       name="testimonial_reject"),
    path("admin-panel/testimonials/<int:pk>/feature",   panel.testimonial_feature,      name="testimonial_feature"),
    path("admin-panel/testimonials/<int:pk>/delete",    panel.testimonial_delete_admin, name="testimonial_delete_admin"),
    path("admin-panel/orders/<int:pk>/invoice", panel.order_invoice, name="order_invoice"),
    path("admin-panel/change-password", panel.admin_change_password, name="admin_change_password"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    # Seed placeholder imagery is stored at static/seed/ but referenced by the
    # original app's absolute "/seed/..." paths, so map that prefix too.
    urlpatterns += static("/seed/", document_root=settings.STATICFILES_DIRS[0] / "seed")
