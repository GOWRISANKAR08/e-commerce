"""Template globals available on every page (site name, cart count, nav)."""
from django.conf import settings

from core.nav import ADMIN_NAV
from core.utils import inr


def _site_cfg():
    """Read live settings from DB, fall back to settings.py."""
    try:
        from store.models import SiteSettings
        cfg = SiteSettings.get()
        return {
            "name":               cfg.store_name,
            "tagline":            cfg.store_tagline,
            "email":              cfg.business_email,
            "phone":              cfg.support_phone,
            "address":            cfg.store_address,
            "logo_url":           cfg.logo_url,
            "free_shipping":      cfg.free_shipping_above,
            "shipping_fee":       cfg.default_shipping_charge,
            "cod_enabled":        cfg.cod_enabled,
            "order_id_prefix":    cfg.order_id_prefix,
            "currency":           cfg.currency,
            "timezone":           cfg.timezone,
            "language":           cfg.language,
            "date_format":        cfg.date_format,
            "weight_unit":        cfg.weight_unit,
            "processing_time":    cfg.processing_time,
            "estimated_delivery": cfg.estimated_delivery,
            "gstin":              cfg.gstin,
            "gst_rate":           cfg.default_gst_rate,
            "gst_inclusive":      cfg.prices_inclusive_of_gst,
            "international_ship": cfg.international_shipping,
        }
    except Exception:
        return {
            "name":          getattr(settings, "SITE_NAME", "Spicearog"),
            "free_shipping": getattr(settings, "FREE_DELIVERY_OVER", 499),
            "shipping_fee":  getattr(settings, "SHIPPING_FEE", 49),
            "cod_enabled":   True,
        }


def site_globals(request):
    site = _site_cfg()

    cart_count = 0
    fav_count = 0
    order_counts = {}

    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        cart = getattr(user, "cart", None)
        if cart:
            cart_count = sum(i.qty for i in cart.items.all())
        fav_count = user.favourites.count()

        if getattr(user, "user_type", None) == "ADMIN":
            try:
                from store.models import Order, OrderStatus
                order_counts = {
                    "all":        Order.objects.count(),
                    "pending":    Order.objects.filter(status=OrderStatus.PROCESSING).count(),
                    "processing": Order.objects.filter(
                        status__in=[OrderStatus.ORDER_CONFIRMED, OrderStatus.PACKED]).count(),
                    "shipped":    Order.objects.filter(status=OrderStatus.DISPATCHED).count(),
                    "delivered":  Order.objects.filter(status=OrderStatus.DELIVERED).count(),
                    "cancelled":  Order.objects.filter(status=OrderStatus.CANCELLED).count(),
                    "returns":    Order.objects.filter(status=OrderStatus.REFUNDED).count(),
                }
            except Exception:
                pass

    promo_bar_offers = []
    try:
        from store.models import Coupon
        promo_bar_offers = [
            c for c in Coupon.objects.filter(is_active=True).order_by("-created_at")[:10]
            if c.status_tag == "Active"
        ][:3]
    except Exception:
        pass

    enquiry_unread = 0
    try:
        from store.models import Enquiry
        enquiry_unread = Enquiry.objects.filter(is_read=False).count()
        if enquiry_unread and user and getattr(user, "user_type", None) == "ADMIN":
            order_counts["enquiry_unread"] = enquiry_unread
    except Exception:
        pass

    try:
        from store.models import Testimonial, ReviewStatus
        t_pending = Testimonial.objects.filter(approval_status=ReviewStatus.PENDING).count()
        if t_pending and user and getattr(user, "user_type", None) == "ADMIN":
            order_counts["testimonial_pending"] = t_pending
    except Exception:
        pass

    return {
        # Core site identity — readable everywhere
        "SITE_NAME":        site["name"],
        "SITE_TAGLINE":     site.get("tagline", ""),
        "SITE_EMAIL":       site.get("email", ""),
        "SITE_PHONE":       site.get("phone", ""),
        "SITE_ADDRESS":     site.get("address", ""),
        "SITE_LOGO":        site.get("logo_url", ""),
        "FREE_DELIVERY_OVER": site["free_shipping"],
        "SHIPPING_FEE":     site["shipping_fee"],
        "COD_ENABLED":      site.get("cod_enabled", True),
        "PROCESSING_TIME":    site.get("processing_time", "1-2"),
        "ESTIMATED_DELIVERY": site.get("estimated_delivery", "3-7"),
        "ORDER_ID_PREFIX":  site.get("order_id_prefix", "ORD-"),
        "GST_RATE":         site.get("gst_rate", "5"),
        "GST_INCLUSIVE":    site.get("gst_inclusive", True),
        # Other globals
        "cart_count":       cart_count,
        "fav_count":        fav_count,
        "ADMIN_NAV":        ADMIN_NAV,
        "order_counts":     order_counts,
        "enquiry_unread":   enquiry_unread,
        "promo_bar_offers": promo_bar_offers,
    }
