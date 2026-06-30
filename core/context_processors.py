"""Template globals available on every page (site name, cart count, nav)."""
from django.conf import settings

from core.nav import ADMIN_NAV
from core.utils import inr


def site_globals(request):
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
                    "all": Order.objects.count(),
                    "pending": Order.objects.filter(status=OrderStatus.PROCESSING).count(),
                    "processing": Order.objects.filter(
                        status__in=[OrderStatus.ORDER_CONFIRMED, OrderStatus.PACKED]).count(),
                    "shipped": Order.objects.filter(status=OrderStatus.DISPATCHED).count(),
                    "delivered": Order.objects.filter(status=OrderStatus.DELIVERED).count(),
                    "cancelled": Order.objects.filter(status=OrderStatus.CANCELLED).count(),
                    "returns": Order.objects.filter(status=OrderStatus.REFUNDED).count(),
                }
            except Exception:
                pass

    return {
        "SITE_NAME": settings.SITE_NAME,
        "FREE_DELIVERY_OVER": settings.FREE_DELIVERY_OVER,
        "SHIPPING_FEE": settings.SHIPPING_FEE,
        "cart_count": cart_count,
        "fav_count": fav_count,
        "ADMIN_NAV": ADMIN_NAV,
        "order_counts": order_counts,
    }
