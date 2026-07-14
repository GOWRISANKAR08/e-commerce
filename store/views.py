"""
Storefront views — ports the public (site) pages and storefront APIs:
home, products, product detail, cart, favourites, orders/checkout, reviews,
account, blogs, categories, policies and the enquiry/contact form.
"""
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Min, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Status, UserAddress
from core.utils import gen_code
from .models import (
    Banner, BannerType, Blog, Cart, CartItem, Category, CMSRevision, ComboPackage, Coupon,
    CouponType, Enquiry, FaqCategory, Favourite, Notification, Order, OrderEvent, OrderItem,
    PaymentAttempt, PaymentAttemptStatus, PaymentMode, PaymentStatus, PendingOrderStatus,
    Policy, PolicyType, Product, ProductVariant, RazorpayPendingOrder, Review, ReviewImage,
    ReviewStatus, SiteSettings, TeamMember, Testimonial, Faq, OrderStatus,
)

_SESSION_COUPON = "cart_coupon_code"


def _shipping_cfg():
    """Return (free_shipping_above, default_shipping_charge) from DB settings."""
    try:
        from .models import SiteSettings
        cfg = SiteSettings.get()
        return cfg.free_shipping_above, cfg.default_shipping_charge
    except Exception:
        return getattr(settings, "FREE_DELIVERY_OVER", 499), getattr(settings, "SHIPPING_FEE", 49)


def _razorpay_keys():
    """Return (key_id, key_secret) from IntegrationConfig, fall back to settings.py."""
    try:
        from .models import IntegrationConfig
        rows = {r.key: r.value for r in IntegrationConfig.objects.filter(integration="RAZORPAY")}
        key_id, key_secret = rows.get("key_id", ""), rows.get("key_secret", "")
        if key_id and key_secret:
            return key_id, key_secret
    except Exception:
        pass
    return getattr(settings, "RAZORPAY_KEY_ID", ""), getattr(settings, "RAZORPAY_KEY_SECRET", "")


def _active_offers(limit=8):
    """Return currently active coupons, evaluated in Python."""
    return [c for c in Coupon.objects.filter(is_active=True).order_by("-created_at") if c.status_tag == "Active"][:limit]


def _resolve_session_coupon(request, subtotal, shipping):
    """
    Read cart_coupon_code from session, validate, and return
    (coupon_obj, coupon_discount, coupon_free_ship, updated_shipping).
    Clears the session key if the coupon is no longer valid.
    """
    code = request.session.get(_SESSION_COUPON, "")
    if not code or subtotal <= 0:
        return None, 0, False, shipping
    try:
        c = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        request.session.pop(_SESSION_COUPON, None)
        return None, 0, False, shipping

    if c.status_tag != "Active" or subtotal < c.min_order_value:
        request.session.pop(_SESSION_COUPON, None)
        return None, 0, False, shipping

    if c.max_uses > 0 and c.used_count >= c.max_uses:
        request.session.pop(_SESSION_COUPON, None)
        return None, 0, False, shipping

    if c.coupon_type == CouponType.FREE_SHIPPING:
        return c, 0, True, 0
    discount = c.compute_discount(subtotal)
    return c, discount, False, shipping


# --------------------------------------------------------------------------- #
# Home / landing page  (port of (site)/page.tsx + api/home)
# --------------------------------------------------------------------------- #
def home(request):
    hero_banners = list(
        Banner.objects.filter(type=BannerType.HOME_BANNER, status=Status.ACTIVE).order_by("position")[:5]
    )
    categories = list(Category.objects.filter(status=Status.ACTIVE).order_by("position")[:8])
    best_sellers = list(
        Product.objects.filter(status=Status.ACTIVE, top_seller=True)
        .prefetch_related("variants", "reviews").order_by("position")[:6]
    )
    new_arrivals = list(
        Product.objects.filter(status=Status.ACTIVE)
        .prefetch_related("variants", "reviews").order_by("-created_at")[:6]
    )
    trending = list(
        Product.objects.filter(status=Status.ACTIVE, badge__iexact="Trending")
        .prefetch_related("variants", "reviews").order_by("position")[:6]
    )
    if not trending:
        trending = list(
            Product.objects.filter(status=Status.ACTIVE)
            .prefetch_related("variants", "reviews").order_by("-updated_at")[:6]
        )
    flash_deals = list(
        Product.objects.filter(status=Status.ACTIVE, badge__icontains="Flash")
        .prefetch_related("variants", "reviews").order_by("position")[:4]
    )
    if not flash_deals:
        flash_deals = list(
            Product.objects.filter(status=Status.ACTIVE, is_featured=True)
            .prefetch_related("variants", "reviews").order_by("position")[:4]
        )
    combos = list(
        ComboPackage.objects.filter(status=ComboPackage.Status.ACTIVE)
        .prefetch_related("items__variant__product__reviews", "images")
        .order_by("position")[:4]
    )
    for _c in combos:
        _ratings = [
            r.rating for ci in _c.items.all()
            for r in ci.variant.product.reviews.all()
            if r.status == ReviewStatus.APPROVED and not r.is_flagged
        ]
        _c.avg_rating = round(sum(_ratings) / len(_ratings), 1) if _ratings else 0
        _c.review_count = len(_ratings)
        _c.avg_rating_int = round(_c.avg_rating)
    offer_banners = list(
        Banner.objects.filter(type=BannerType.OFFER_BANNER, status=Status.ACTIVE).order_by("position")[:2]
    )
    testimonials = list(
        Testimonial.objects.filter(
            approval_status=ReviewStatus.APPROVED
        ).select_related('order').order_by('-is_featured', 'position', '-created_at')[:12]
    )
    fav_ids = _fav_ids(request.user)
    active_offers = _active_offers(limit=6)
    return render(request, "site/home.html", {
        "hero_banners": hero_banners,
        "categories": categories,
        "best_sellers": best_sellers,
        "new_arrivals": new_arrivals,
        "trending": trending,
        "flash_deals": flash_deals,
        "combos": combos,
        "offer_banners": offer_banners,
        "testimonials": testimonials,
        "fav_ids": fav_ids,
        "active_offers": active_offers,
        "story_stats": [("200+", "Organic Products"), ("50+", "Partner Farms"),
                        ("25K+", "Happy Customers"), ("100%", "Natural Ingredients")],
    })


def _fav_ids(user):
    if user.is_authenticated:
        return set(user.favourites.values_list("product_id", flat=True))
    return set()


# --------------------------------------------------------------------------- #
# Product listing (port of api/products + (site)/products)
# --------------------------------------------------------------------------- #
def _safe_num(s, default=None):
    if not s and s != 0:
        return default
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _page_range(page_obj):
    total = page_obj.paginator.num_pages
    current = page_obj.number
    pages = sorted({1, 2, max(1, current - 1), current, min(total, current + 1), max(1, total - 1), total})
    result, prev = [], None
    for p in pages:
        if prev is not None and p - prev > 1:
            result.append(None)
        result.append(p)
        prev = p
    return result


def products(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "popularity")
    price_range = request.GET.get("price_range", "").strip()
    min_rating = request.GET.get("rating", "").strip()
    price_min_raw = request.GET.get("price_min", "").strip()
    price_max_raw = request.GET.get("price_max", "").strip()

    active_var_prefetch = Prefetch(
        "variants",
        queryset=ProductVariant.objects.filter(status=Status.ACTIVE).order_by("position"),
        to_attr="active_variants_list",
    )
    qs = (Product.objects
          .filter(status=Status.ACTIVE)
          .select_related("category")
          .prefetch_related(active_var_prefetch)
          .annotate(
              min_price=Min("variants__selling_price",
                            filter=Q(variants__status=Status.ACTIVE)),
              avg_r=Avg("reviews__rating",
                        filter=Q(reviews__status=ReviewStatus.APPROVED)),
              review_cnt=Count("reviews",
                               filter=Q(reviews__status=ReviewStatus.APPROVED)),
          ))

    if q:
        qs = qs.filter(name__icontains=q)
    if category:
        qs = qs.filter(category__slug=category)

    _price_map = {
        "under200": Q(min_price__lt=200),
        "200-500":  Q(min_price__gte=200, min_price__lte=500),
        "500-1000": Q(min_price__gte=500, min_price__lte=1000),
        "above1000": Q(min_price__gt=1000),
    }
    if price_range in _price_map:
        qs = qs.filter(_price_map[price_range])
    else:
        # Custom slider range
        pmin = _safe_num(price_min_raw, None)
        pmax = _safe_num(price_max_raw, None)
        if pmin is not None:
            qs = qs.filter(min_price__gte=pmin)
        if pmax is not None:
            qs = qs.filter(min_price__lte=pmax)

    if min_rating:
        try:
            qs = qs.filter(avg_r__gte=int(min_rating))
        except ValueError:
            pass

    _sort_map = {
        "popularity": "position",
        "newest": "-created_at",
        "price_low": "min_price",
        "price_high": "-min_price",
        "rating": "-avg_r",
    }
    qs = qs.order_by(_sort_map.get(sort, "position"))

    all_categories = (Category.objects
                      .filter(status=Status.ACTIVE)
                      .annotate(product_count=Count(
                          "products", filter=Q(products__status=Status.ACTIVE)))
                      .order_by("position"))
    total_all = Product.objects.filter(status=Status.ACTIVE).count()

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page", 1))

    active_filters = []
    _price_labels = {
        "under200": "Under ₹200", "200-500": "₹200 – ₹500",
        "500-1000": "₹500 – ₹1000", "above1000": "Above ₹1000",
    }
    if price_range in _price_labels:
        active_filters.append(("price_range", _price_labels[price_range]))
    elif price_min_raw or price_max_raw:
        lo = f"₹{int(float(price_min_raw))}" if price_min_raw else "₹0"
        hi = f"₹{int(float(price_max_raw))}" if price_max_raw else "any"
        active_filters.append(("price_range", f"{lo} – {hi}"))
    if min_rating:
        active_filters.append(("rating", f"{min_rating}★ & above"))
    if category:
        cat_obj = next((c for c in all_categories if c.slug == category), None)
        if cat_obj:
            active_filters.append(("category", cat_obj.name))
    if q:
        active_filters.append(("q", f'"{q}"'))

    params = request.GET.copy()
    params.pop("page", None)
    query_string = params.urlencode()

    promo = next(iter(_active_offers(1)), None)

    return render(request, "site/products.html", {
        "page_obj": page,
        "q": q,
        "active_category": category,
        "categories": all_categories,
        "total_all": total_all,
        "fav_ids": _fav_ids(request.user),
        "total": paginator.count,
        "sort": sort,
        "price_range": price_range,
        "price_min": _safe_num(price_min_raw) or 0,
        "price_max": _safe_num(price_max_raw) or 5000,
        "min_rating": min_rating,
        "active_filters": active_filters,
        "query_string": query_string,
        "page_range": _page_range(page),
        "promo": promo,
        "price_options": [
            ("under200", "Under ₹200"),
            ("200-500", "₹200 – ₹500"),
            ("500-1000", "₹500 – ₹1000"),
            ("above1000", "Above ₹1000"),
        ],
        "rating_options": [
            {"value": "5", "stars": "★★★★★"},
            {"value": "4", "stars": "★★★★☆"},
            {"value": "3", "stars": "★★★☆☆"},
            {"value": "2", "stars": "★★☆☆☆"},
        ],
    })


def categories(request):
    cats = Category.objects.filter(status=Status.ACTIVE).order_by("position")
    return render(request, "site/categories.html", {"categories": cats})


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related("variants", "images", "reviews__user", "reviews__images"),
        slug=slug, status=Status.ACTIVE,
    )
    related = (Product.objects.filter(category=product.category, status=Status.ACTIVE)
               .exclude(id=product.id).order_by("position")[:settings.RELATED_PRODUCT_LIMIT])
    # Public reviews: only APPROVED, not flagged
    reviews = product.reviews.filter(status=ReviewStatus.APPROVED, is_flagged=False).order_by("-created_at")
    # Rating distribution for approved reviews
    approved_ratings = list(reviews.values_list("rating", flat=True))
    total_reviews = len(approved_ratings)
    avg_rating = round(sum(approved_ratings) / total_reviews, 1) if approved_ratings else 0
    rating_dist = {i: approved_ratings.count(i) for i in range(1, 6)}

    can_review = False
    already_reviewed = False
    user_review = None
    if request.user.is_authenticated:
        user_review = product.reviews.filter(user=request.user).first()
        already_reviewed = user_review is not None
        purchased = OrderItem.objects.filter(
            product=product, order__user=request.user,
            order__status=OrderStatus.DELIVERED
        ).exists()
        can_review = purchased and not already_reviewed
    return render(request, "site/product_detail.html", {
        "product": product, "variants": product.active_variants, "images": product.images.all(),
        "related": related, "reviews": reviews, "can_review": can_review,
        "already_reviewed": already_reviewed, "user_review": user_review,
        "total_reviews": total_reviews, "avg_rating": avg_rating, "rating_dist": rating_dist,
        "favourited": request.user.is_authenticated and
        product.favourites.filter(user=request.user).exists(),
        "active_offers": _active_offers(limit=4),
    })


def product_quick_view(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related("variants", "images", "reviews"),
        slug=slug, status=Status.ACTIVE,
    )
    approved = product.reviews.filter(status=ReviewStatus.APPROVED, is_flagged=False)
    ratings = list(approved.values_list("rating", flat=True))
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    return JsonResponse({
        "ok": True,
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "image": str(product.image) if product.image else "",
        "images": [str(im.image) for im in product.images.all()],
        "badge": product.badge or "",
        "category": product.category.name if product.category else "",
        "description": product.description or "",
        "avg_rating": avg_rating,
        "total_reviews": len(ratings),
        "variants": [
            {
                "id": v.id,
                "variant": str(v.variant),
                "selling_price": float(v.selling_price),
                "mrp_price": float(v.mrp_price),
                "discount_pct": v.discount_pct,
                "stock_status": v.stock_status,
                "stock": v.stock,
                "va_code": v.va_code or "",
            }
            for v in product.active_variants
        ],
        "offers": [
            {
                "code": o.code,
                "type": o.coupon_type,
                "value": float(o.discount_value),
                "min_order": float(o.min_order_value or 0),
            }
            for o in _active_offers(limit=4)
        ],
        "favourited": (
            request.user.is_authenticated
            and product.favourites.filter(user=request.user).exists()
        ),
    })


# --------------------------------------------------------------------------- #
# Favourites (toggle)  (port of api/favourites)
# --------------------------------------------------------------------------- #
@require_POST
@login_required
def favourite_toggle(request):
    product_id = _body(request).get("productId")
    product = get_object_or_404(Product, id=product_id)
    fav = Favourite.objects.filter(user=request.user, product=product).first()
    if fav:
        fav.delete()
        favourited = False
    else:
        Favourite.objects.create(user=request.user, product=product)
        favourited = True
    if _is_ajax(request):
        return JsonResponse({"favourited": favourited})
    messages.success(request, "Added to favourites." if favourited else "Removed from favourites.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def favourites(request):
    favs = (Favourite.objects.filter(user=request.user)
            .select_related("product").prefetch_related("product__variants").order_by("-created_at"))
    return render(request, "site/favourites.html", {
        "favourites": favs, "fav_ids": _fav_ids(request.user),
    })


# --------------------------------------------------------------------------- #
# Cart  (port of api/cart)
# --------------------------------------------------------------------------- #
def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _cart_has_combo(user):
    cart = getattr(user, "cart", None)
    if not cart:
        return False
    return cart.items.filter(combo__isnull=False).exists()


@login_required
def cart_view(request):
    cart = _get_or_create_cart(request.user)
    items = list(cart.items.select_related("variant", "variant__product", "combo").all())
    subtotal = sum(i.line_total for i in items)
    _free_over, _ship_fee = _shipping_cfg()
    shipping = 0 if subtotal >= _free_over else _ship_fee

    coupon_obj, coupon_discount, coupon_free_ship, shipping = _resolve_session_coupon(
        request, subtotal, shipping)
    grand_total = max(0.0, subtotal + shipping - coupon_discount)

    product_savings = sum(
        (i.variant.mrp_price - i.variant.selling_price) * i.qty
        for i in items
        if i.variant.mrp_price > i.variant.selling_price
    )
    cart_product_ids = {i.variant.product_id for i in items}
    recommendations = list(
        Product.objects.filter(status=Status.ACTIVE)
        .exclude(id__in=cart_product_ids)
        .prefetch_related("variants", "reviews")
        .order_by("-updated_at")[:6]
    )

    has_combo = any(i.combo_id for i in items)
    return render(request, "site/cart.html", {
        "items": items, "subtotal": subtotal, "shipping": shipping,
        "grand_total": grand_total,
        "coupon_obj": coupon_obj,
        "coupon_discount": coupon_discount,
        "coupon_free_ship": coupon_free_ship,
        "applied_code": request.session.get(_SESSION_COUPON, ""),
        "active_offers": _active_offers(limit=6),
        "product_savings": product_savings,
        "recommendations": recommendations,
        "fav_ids": _fav_ids(request.user),
        "FREE_DELIVERY_OVER": _free_over,
        "SHIPPING_FEE": _ship_fee,
        "has_combo": has_combo,
    })


@require_POST
@login_required
def cart_add(request):
    data = _body(request)
    variant = get_object_or_404(ProductVariant, id=data.get("variantId"))
    try:
        qty = int(data.get("qty", 1))
    except (TypeError, ValueError):
        qty = 1
    cart = _get_or_create_cart(request.user)
    item, created = CartItem.objects.get_or_create(
        cart=cart, variant=variant,
        defaults={"product": variant.product, "qty": max(qty, 1), "price": variant.selling_price},
    )
    if not created:
        item.qty = qty if qty > 0 else 1
        item.price = variant.selling_price
        item.save()
    count = sum(i.qty for i in cart.items.all())
    if _is_ajax(request):
        return JsonResponse({"ok": True, "count": count})
    messages.success(request, "Added to cart.")
    return redirect(request.META.get("HTTP_REFERER", "/cart"))


@require_POST
@login_required
def cart_remove(request):
    item_id = _body(request).get("itemId") or request.POST.get("itemId")
    cart = getattr(request.user, "cart", None)
    if cart:
        CartItem.objects.filter(id=item_id, cart=cart).delete()
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect("/cart")


@require_POST
@login_required
def combo_cart_remove(request, slug):
    combo = get_object_or_404(ComboPackage, slug=slug)
    cart = getattr(request.user, "cart", None)
    if cart:
        CartItem.objects.filter(cart=cart, combo=combo).delete()
    if _is_ajax(request):
        count = sum(i.qty for i in cart.items.all()) if cart else 0
        return JsonResponse({"ok": True, "cart_count": count})
    return redirect("/cart")


@require_POST
@login_required
def coupon_apply(request):
    data = _body(request)
    code = (data.get("code") or "").strip().upper()
    try:
        subtotal = float(data.get("subtotal") or 0)
    except (ValueError, TypeError):
        subtotal = 0

    if not code:
        return JsonResponse({"ok": False, "error": "Please enter a coupon code."})

    if _cart_has_combo(request.user):
        return JsonResponse({"ok": False, "error": "Coupon codes cannot be applied to Combo Products because they already include a special bundle discount."})

    try:
        c = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Invalid coupon code. Please check and try again."})

    tag = c.status_tag
    if tag == "Inactive":
        return JsonResponse({"ok": False, "error": "This coupon is currently inactive."})
    if tag == "Scheduled":
        sdate = c.valid_from.strftime("%-d %b %Y") if c.valid_from else ""
        return JsonResponse({"ok": False, "error": f"This offer starts on {sdate}."})
    if tag == "Expired":
        return JsonResponse({"ok": False, "error": "This coupon has expired."})

    if c.max_uses > 0 and c.used_count >= c.max_uses:
        return JsonResponse({"ok": False, "error": "This coupon's usage limit has been reached."})

    if c.per_user_limit > 0 and request.user.is_authenticated:
        used_by_user = Order.objects.filter(user=request.user, coupon=c).count()
        if used_by_user >= c.per_user_limit:
            return JsonResponse({"ok": False, "error": f"You have already used this coupon {c.per_user_limit} time(s)."})

    if subtotal < c.min_order_value:
        return JsonResponse({"ok": False,
                             "error": f"Add ₹{c.min_order_value - subtotal:.0f} more to use this coupon (min cart: ₹{c.min_order_value:.0f})."})

    request.session[_SESSION_COUPON] = code

    _free_over, _ship_fee = _shipping_cfg()
    base_shipping = 0 if subtotal >= _free_over else _ship_fee
    if c.coupon_type == CouponType.FREE_SHIPPING:
        discount = base_shipping
        shipping = 0
        free_ship = True
    else:
        discount = c.compute_discount(subtotal)
        shipping = base_shipping
        free_ship = False

    grand_total = max(0.0, subtotal + shipping - discount)

    return JsonResponse({
        "ok": True,
        "code": code,
        "name": c.name or code,
        "type": c.coupon_type,
        "discount": round(discount, 2),
        "shipping": round(shipping, 2),
        "grand_total": round(grand_total, 2),
        "free_ship": free_ship,
        "message": f"“{code}” applied! You save ₹{discount:.0f}.",
    })


@login_required
def coupon_remove(request):
    request.session.pop(_SESSION_COUPON, None)
    cart = getattr(request.user, "cart", None)
    subtotal = 0
    if cart:
        subtotal = sum(i.line_total for i in cart.items.select_related("variant").all())
    _free_over, _ship_fee = _shipping_cfg()
    shipping = 0 if subtotal >= _free_over else _ship_fee
    return JsonResponse({"ok": True, "subtotal": subtotal, "shipping": shipping,
                         "grand_total": subtotal + shipping})


# --------------------------------------------------------------------------- #
# Combo Products
# --------------------------------------------------------------------------- #
def combo_list(request):
    qs = (ComboPackage.objects
          .filter(status=ComboPackage.Status.ACTIVE)
          .prefetch_related("items__variant__product", "images"))

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(tags__icontains=q) | Q(short_description__icontains=q)
        )

    sort = request.GET.get("sort", "position")
    if sort == "price_asc":
        qs = qs.order_by("selling_price")
    elif sort == "price_desc":
        qs = qs.order_by("-selling_price")
    elif sort == "newest":
        qs = qs.order_by("-created_at")
    elif sort == "savings":
        qs = qs.order_by("-selling_price")
    else:
        qs = qs.order_by("position", "-created_at")

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(request, "site/combos.html", {
        "combos": page_obj,
        "page_obj": page_obj,
        "sort": sort,
        "q": q,
        "total": paginator.count,
        "active_offers": _active_offers(limit=4),
    })


def combo_detail(request, slug):
    combo = get_object_or_404(
        ComboPackage.objects.prefetch_related(
            "items__variant__product__reviews",
            "items__variant__product",
            "images",
        ),
        slug=slug,
        status=ComboPackage.Status.ACTIVE,
    )
    ratings = []
    for ci in combo.items.all():
        ratings.extend(
            ci.variant.product.reviews.filter(
                status=ReviewStatus.APPROVED, is_flagged=False
            ).values_list("rating", flat=True)
        )
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    return render(request, "site/combo_detail.html", {
        "combo": combo,
        "avg_rating": avg_rating,
        "total_reviews": len(ratings),
        "active_offers": _active_offers(limit=4),
    })


@require_POST
@login_required
def combo_cart_add(request):
    data = _body(request)
    slug = data.get("slug", "")
    try:
        qty_mul = max(1, min(10, int(data.get("qty", 1))))
    except (ValueError, TypeError):
        qty_mul = 1

    combo = get_object_or_404(ComboPackage, slug=slug, status=ComboPackage.Status.ACTIVE)
    items = list(combo.items.select_related("variant__product").all())
    if not items:
        return JsonResponse({"ok": False, "error": "This combo has no products."})

    for ci in items:
        needed = ci.quantity * qty_mul
        if ci.variant.stock < needed:
            return JsonResponse({
                "ok": False,
                "error": f"{ci.variant.product.name} ({ci.variant.variant}) is out of stock.",
            })

    original_total = sum(ci.variant.selling_price * ci.quantity for ci in items) or 1.0
    ratio = combo.selling_price / original_total

    cart = _get_or_create_cart(request.user)
    for ci in items:
        item_price = round(ci.variant.selling_price * ratio, 2)
        CartItem.objects.update_or_create(
            cart=cart,
            variant=ci.variant,
            defaults={
                "product": ci.variant.product,
                "qty": ci.quantity * qty_mul,
                "price": item_price,
                "combo": combo,
            },
        )

    cart_count = sum(i.qty for i in cart.items.all())
    return JsonResponse({"ok": True, "cart_count": cart_count})


# --------------------------------------------------------------------------- #
# Orders / checkout  (port of api/orders)
# --------------------------------------------------------------------------- #
@login_required
def orders(request):
    qs = (Order.objects.filter(user=request.user)
          .prefetch_related("items", "items__product").order_by("-created_at"))
    reviewed_ids = set(
        Review.objects.filter(user=request.user).values_list("product_id", flat=True)
    )
    return render(request, "site/orders.html", {"orders": qs, "reviewed_ids": reviewed_ids})


# Status → progress-step integer (for the visual stepper on the detail page)
_STATUS_STEP = {
    "PROCESSING":      1,
    "ORDER_CONFIRMED": 2,
    "PACKED":          3,
    "DISPATCHED":      4,
    "DELIVERED":       5,
}

_CANCEL_ALLOWED = {"PROCESSING", "ORDER_CONFIRMED"}
_RETURN_ALLOWED = {"DELIVERED"}


@login_required
def order_detail_customer(request, order_id):
    import json as _json
    order = get_object_or_404(
        Order.objects.select_related("user", "coupon")
             .prefetch_related("items__product", "items__variant", "items__combo",
                               "events", "notes", "refunds"),
        order_id=order_id,
        user=request.user,
    )

    try:
        shipping = _json.loads(order.shipping_address)
    except Exception:
        shipping = {"address": order.shipping_address}

    items = list(order.items.all())
    combos_map = {}
    regular_items = []
    for it in items:
        if it.combo_id:
            combos_map.setdefault(it.combo_id, {"combo": it.combo, "items": []})["items"].append(it)
        else:
            regular_items.append(it)

    reviewed_ids = set(
        Review.objects.filter(user=request.user).values_list("product_id", flat=True)
    )

    events = list(order.events.order_by("created_at"))
    notes  = list(order.notes.filter(is_internal=False).order_by("created_at"))
    refunds = list(order.refunds.all())
    total_refunded = round(sum(r.amount for r in refunds), 2)

    cfg         = SiteSettings.get()
    show_gst    = cfg.show_gst_in_invoice
    prices_incl = cfg.prices_inclusive_of_gst
    default_gst = float(cfg.default_gst_rate or 5)

    total_gst = 0.0
    for it in items:
        gst_rate = float(it.combo.gst_rate if it.combo else default_gst)
        line = float(it.net_total)
        if prices_incl:
            total_gst += line * gst_rate / (100 + gst_rate)
        else:
            total_gst += line * gst_rate / 100

    return render(request, "site/order_detail.html", {
        "order":          order,
        "shipping":       shipping,
        "regular_items":  regular_items,
        "combos":         list(combos_map.values()),
        "items":          items,
        "reviewed_ids":   reviewed_ids,
        "events":         events,
        "notes":          notes,
        "refunds":        refunds,
        "total_refunded": total_refunded,
        "cancellable":    order.status in _CANCEL_ALLOWED,
        "returnable":     (order.status in _RETURN_ALLOWED
                           and order.payment_status == PaymentStatus.PAID),
        "show_gst":       show_gst,
        "total_gst":      round(total_gst, 2),
        "status_step":    _STATUS_STEP.get(order.status, 0),
        "savings":        order.discount,
        "PaymentMode":    PaymentMode,
        "OrderStatus":    OrderStatus,
        "PaymentStatus":  PaymentStatus,
    })


@login_required
@require_POST
def order_cancel_customer(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if order.status not in _CANCEL_ALLOWED:
        messages.error(request, "This order cannot be cancelled at its current stage.")
        return redirect(f"/orders/{order_id}")
    for it in order.items.select_related("variant").all():
        it.variant.stock += it.qty
        it.variant.save(update_fields=["stock"])
    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    OrderEvent.objects.create(
        order=order,
        title="Order Cancelled",
        description="Cancelled by customer.",
        actor_name=request.user.full_name,
    )
    messages.success(request, f"Order {order_id} has been cancelled.")
    return redirect(f"/orders/{order_id}")


@login_required
@require_POST
def order_reorder(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    try:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        added = 0
        for it in order.items.select_related("variant", "product").all():
            if it.variant.stock > 0:
                ci, created = CartItem.objects.get_or_create(
                    cart=cart, variant=it.variant,
                    defaults={
                        "product": it.product,
                        "qty": it.qty,
                        "price": it.variant.selling_price,
                    },
                )
                if not created:
                    ci.qty += it.qty
                    ci.price = it.variant.selling_price
                    ci.save(update_fields=["qty", "price"])
                added += 1
        if added:
            messages.success(request, f"{added} item(s) added to your cart.")
        else:
            messages.warning(request, "Sorry, all items in this order are currently out of stock.")
    except Exception:
        messages.error(request, "Could not reorder. Please add items to cart manually.")
    return redirect("/cart")


@login_required
def order_invoice_customer(request, order_id):
    """Standalone print-ready invoice — customer-accessible, same template as admin."""
    import json as _json
    order = get_object_or_404(
        Order.objects.select_related("user", "coupon")
             .prefetch_related("items__product", "items__variant", "items__combo", "refunds"),
        order_id=order_id,
        user=request.user,
    )
    cfg = SiteSettings.get()
    try:
        addr = _json.loads(order.shipping_address)
    except Exception:
        addr = {"address": order.shipping_address}

    default_gst = float(cfg.default_gst_rate or 5)
    show_gst    = cfg.show_gst_in_invoice
    prices_incl = cfg.prices_inclusive_of_gst

    enriched      = []
    total_gst     = 0.0
    total_taxable = 0.0
    for it in order.items.all():
        gst_rate = float(it.combo.gst_rate if it.combo else default_gst)
        line = float(it.net_total)
        if prices_incl:
            gst_amt = round(line * gst_rate / (100 + gst_rate), 2)
        else:
            gst_amt = round(line * gst_rate / 100, 2)
        taxable = round(line - gst_amt if prices_incl else line, 2)
        total_gst     += gst_amt
        total_taxable += taxable
        enriched.append({"item": it, "gst_rate": gst_rate, "gst_amt": gst_amt, "taxable": taxable})

    combos_map    = {}
    regular_items = []
    for eitem in enriched:
        it = eitem["item"]
        if it.combo_id:
            if it.combo_id not in combos_map:
                combos_map[it.combo_id] = {"combo": it.combo, "items": []}
            combos_map[it.combo_id]["items"].append(eitem)
        else:
            regular_items.append(eitem)

    refunds        = list(order.refunds.all())
    total_refunded = sum(r.amount for r in refunds)

    return render(request, "panel/invoice.html", {
        "order":          order,
        "addr":           addr,
        "cfg":            cfg,
        "regular_items":  regular_items,
        "combos":         list(combos_map.values()),
        "refunds":        refunds,
        "total_refunded": round(total_refunded, 2),
        "show_gst":       show_gst,
        "prices_incl":    prices_incl,
        "total_gst":      round(total_gst, 2),
        "total_taxable":  round(total_taxable, 2),
        "PaymentMode":    PaymentMode,
        "OrderStatus":    OrderStatus,
        "PaymentStatus":  PaymentStatus,
    })


def _create_order_from_pending(pending, rzp_payment_id):
    """
    Convert a RazorpayPendingOrder into a real Order after confirmed payment.
    Must be called inside a transaction.atomic() block.
    """
    from django.db import models as _m
    cart_items = json.loads(pending.cart_snapshot)

    order = Order.objects.create(
        order_id=pending.order_code,
        invoice_no=f"INV-{pending.order_code}",
        user=pending.user,
        sub_total=pending.sub_total,
        shipping_amount=pending.shipping_amount,
        grand_total=pending.grand_total,
        coupon=pending.coupon,
        coupon_discount=pending.coupon_discount,
        payment_mode=PaymentMode.RAZORPAY,
        razorpay_order_id=pending.razorpay_order_id,
        razorpay_payment_id=rzp_payment_id,
        payment_status=PaymentStatus.PAID,
        shipping_address=pending.shipping_address,
        no_of_product=sum(i["qty"] for i in cart_items),
    )

    if pending.coupon_id:
        Coupon.objects.filter(pk=pending.coupon_id).update(
            used_count=_m.F("used_count") + 1)

    combo_pks = set()
    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            product_id=item["product_id"],
            variant_id=item["variant_id"],
            combo_id=item.get("combo_id"),
            name=item["name"],
            variant_label=item["variant_label"],
            price=item["price"],
            qty=item["qty"],
            net_total=item["net_total"],
        )
        if item.get("combo_id"):
            combo_pks.add(item["combo_id"])

    if combo_pks:
        from django.db import models as _dm
        ComboPackage.objects.filter(pk__in=combo_pks).update(
            orders_count=_dm.F("orders_count") + 1)

    OrderEvent.objects.create(
        order=order,
        title="Order Placed",
        description=f"Order placed via Razorpay. Payment ID: {rzp_payment_id}",
        actor_name=pending.user.full_name,
    )

    pending.status = PendingOrderStatus.PAID
    pending.save(update_fields=["status"])

    PaymentAttempt.objects.filter(
        pending_order=pending,
        status=PaymentAttemptStatus.INITIATED,
    ).update(
        status=PaymentAttemptStatus.SUCCESS,
        razorpay_payment_id=rzp_payment_id,
    )

    return order


@login_required
def checkout(request):
    cart = _get_or_create_cart(request.user)
    items = list(cart.items.select_related(
        "variant", "variant__product", "product", "combo").all())
    if not items:
        messages.error(request, "Your cart is empty.")
        return redirect("/cart")
    subtotal = sum(i.line_total for i in items)
    product_savings = sum(
        max(0, (i.variant.mrp_price - i.price)) * i.qty for i in items)
    _free_over, _ship_fee = _shipping_cfg()
    _rzp_key_id, _rzp_key_secret = _razorpay_keys()
    base_shipping = 0 if subtotal >= _free_over else _ship_fee

    coupon_obj, coupon_discount, coupon_free_ship, shipping = _resolve_session_coupon(
        request, subtotal, base_shipping)
    grand_total = max(0.0, subtotal + shipping - coupon_discount)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        payment_mode = request.POST.get("paymentMode", PaymentMode.COD)

        # Build shipping address — prefer saved address over form fields
        selected_addr_id = request.POST.get("selectedAddressId", "").strip()
        if selected_addr_id:
            try:
                saved = request.user.addresses.get(pk=selected_addr_id)
                full_addr = " ".join(filter(None, [saved.street_flat, saved.address, saved.landmark]))
                shipping_address = {
                    "name": request.user.full_name,
                    "mobile": request.user.mobile or "",
                    "address": full_addr or saved.address,
                    "city": saved.city,
                    "pinCode": saved.pin_code,
                }
            except UserAddress.DoesNotExist:
                selected_addr_id = ""

        if not selected_addr_id:
            name = request.POST.get("deliveryName", request.user.full_name).strip()
            mobile = request.POST.get("deliveryMobile", request.user.mobile or "").strip()
            line1 = request.POST.get("addressLine1", "").strip()
            line2 = request.POST.get("addressLine2", "").strip()
            city = request.POST.get("deliveryCity", "").strip()
            pincode = request.POST.get("deliveryPincode", "").strip()
            addr_type = request.POST.get("addressType", "Home").strip()

            if not (line1 and city and pincode):
                err = "Please provide a complete delivery address."
                if is_ajax:
                    return JsonResponse({"ok": False, "error": err})
                messages.error(request, err)
                return redirect("/checkout")

            shipping_address = {
                "name": name, "mobile": mobile,
                "address": ", ".join(filter(None, [line1, line2])),
                "city": city, "pinCode": pincode,
            }
            # Save address if requested
            if request.POST.get("saveAddress") == "1":
                is_first = not request.user.addresses.exists()
                UserAddress.objects.create(
                    user=request.user,
                    address_name=addr_type,
                    street_flat=line1, address=line2 or line1,
                    city=city, pin_code=pincode,
                    is_default=is_first,
                )

        # Re-resolve coupon (server-side authoritative)
        co, cd, cfs, ship2 = _resolve_session_coupon(
            request, subtotal, base_shipping)
        coupon_obj = co; coupon_discount = cd; shipping = ship2
        grand_total = max(0.0, subtotal + shipping - coupon_discount)

        order_code = gen_code("SPG")
        razorpay_order_id = None

        if payment_mode == PaymentMode.RAZORPAY:
            try:
                import razorpay as _rzp
                client = _rzp.Client(auth=(_rzp_key_id, _rzp_key_secret))
                rzp_order = client.order.create({
                    "amount": round(grand_total * 100),
                    "currency": "INR",
                    "receipt": order_code,
                })
                razorpay_order_id = rzp_order["id"]
            except Exception:
                err = "Payment gateway error. Please try Cash on Delivery."
                if is_ajax:
                    return JsonResponse({"ok": False, "error": err})
                messages.error(request, err)
                return redirect("/checkout")

            from django.utils import timezone
            from datetime import timedelta
            cart_snapshot = [
                {
                    "variant_id": i.variant_id,
                    "product_id": i.product_id,
                    "combo_id": i.combo_id,
                    "name": i.variant.product.name,
                    "variant_label": str(i.variant.variant),
                    "price": i.price,
                    "qty": i.qty,
                    "net_total": i.line_total,
                }
                for i in items
            ]
            pending = RazorpayPendingOrder.objects.create(
                order_code=order_code,
                razorpay_order_id=razorpay_order_id,
                user=request.user,
                sub_total=subtotal,
                coupon_discount=coupon_discount,
                shipping_amount=shipping,
                grand_total=grand_total,
                coupon=coupon_obj,
                shipping_address=json.dumps(shipping_address),
                cart_snapshot=json.dumps(cart_snapshot),
                expires_at=timezone.now() + timedelta(minutes=30),
            )
            PaymentAttempt.objects.create(
                pending_order=pending,
                user=request.user,
                razorpay_order_id=razorpay_order_id,
                amount=grand_total,
            )
            if is_ajax:
                return JsonResponse({
                    "ok": True, "razorpay": True,
                    "key_id": _rzp_key_id,
                    "razorpay_order_id": razorpay_order_id,
                    "amount": round(grand_total * 100),
                    "order_code": order_code,
                    "name": request.user.full_name,
                    "email": request.user.email or "",
                    "mobile": request.user.mobile or "",
                })
            return redirect("/checkout")

        # COD path — create order immediately
        from django.db import models as _m
        order = Order.objects.create(
            order_id=order_code, invoice_no=f"INV-{order_code}",
            user=request.user,
            sub_total=subtotal, shipping_amount=shipping,
            grand_total=grand_total,
            coupon=coupon_obj, coupon_discount=coupon_discount,
            payment_mode=PaymentMode.COD,
            payment_status=PaymentStatus.PAID,
            shipping_address=json.dumps(shipping_address),
            no_of_product=sum(i.qty for i in items),
        )
        if coupon_obj:
            Coupon.objects.filter(pk=coupon_obj.pk).update(
                used_count=_m.F("used_count") + 1)

        combo_pks = set()
        for i in items:
            OrderItem.objects.create(
                order=order, product=i.product, variant=i.variant,
                combo_id=i.combo_id,
                name=i.variant.product.name, variant_label=str(i.variant.variant),
                price=i.price, qty=i.qty, net_total=i.line_total,
            )
            if i.combo_id:
                combo_pks.add(i.combo_id)

        if combo_pks:
            from django.db import models as _dm
            ComboPackage.objects.filter(pk__in=combo_pks).update(
                orders_count=_dm.F("orders_count") + 1)

        OrderEvent.objects.create(
            order=order,
            title="Order Placed",
            description="Order placed via Cash on Delivery.",
            actor_name=request.user.full_name,
        )

        cart.items.all().delete()
        request.session.pop(_SESSION_COUPON, None)
        messages.success(request, f"Order {order_code} placed successfully!")
        if is_ajax:
            return JsonResponse({"ok": True, "redirect": "/orders"})
        return redirect("/orders")

    addresses = list(request.user.addresses.order_by("-is_default", "-pk"))
    default_addr = next((a for a in addresses if a.is_default), addresses[0] if addresses else None)
    has_combo = any(i.combo_id for i in items)
    return render(request, "site/checkout.html", {
        "items": items, "subtotal": subtotal, "shipping": shipping,
        "grand_total": grand_total, "product_savings": product_savings,
        "addresses": addresses, "default_address": default_addr,
        "coupon_obj": coupon_obj,
        "coupon_discount": coupon_discount,
        "coupon_free_ship": coupon_free_ship,
        "applied_code": request.session.get(_SESSION_COUPON, ""),
        "active_offers": _active_offers(limit=4),
        "RAZORPAY_KEY_ID": _rzp_key_id,
        "has_combo": has_combo,
    })


@require_POST
@login_required
def razorpay_verify(request):
    from django.db import transaction as _tx
    data = _body(request)
    rzp_payment_id = data.get("razorpay_payment_id", "")
    rzp_order_id   = data.get("razorpay_order_id", "")
    rzp_signature  = data.get("razorpay_signature", "")
    order_code     = data.get("order_code", "")

    if not all([rzp_payment_id, rzp_order_id, rzp_signature, order_code]):
        return JsonResponse({"ok": False, "error": "Incomplete payment data."})

    try:
        import razorpay as _rzp
        _rzp_key_id, _rzp_key_secret = _razorpay_keys()
        client = _rzp.Client(auth=(_rzp_key_id, _rzp_key_secret))
        client.utility.verify_payment_signature({
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": rzp_payment_id,
            "razorpay_signature": rzp_signature,
        })
    except Exception:
        PaymentAttempt.objects.filter(
            razorpay_order_id=rzp_order_id, user=request.user,
        ).update(
            status=PaymentAttemptStatus.FAILED,
            failure_reason="Signature verification failed",
            razorpay_payment_id=rzp_payment_id,
        )
        return JsonResponse({"ok": False, "error": "Payment verification failed. Please contact support."})

    with _tx.atomic():
        pending = RazorpayPendingOrder.objects.select_for_update().filter(
            order_code=order_code,
            razorpay_order_id=rzp_order_id,
            user=request.user,
        ).first()

        if not pending:
            return JsonResponse({"ok": False, "error": "Payment session not found."})

        # Idempotency: already processed (e.g. webhook fired first)
        if pending.status == PendingOrderStatus.PAID:
            return JsonResponse({"ok": True, "redirect": f"/orders/{order_code}"})

        if pending.status in (PendingOrderStatus.FAILED, PendingOrderStatus.EXPIRED):
            return JsonResponse({"ok": False, "error": "Payment session expired. Please start a new order."})

        if pending.is_expired():
            pending.status = PendingOrderStatus.EXPIRED
            pending.save(update_fields=["status"])
            return JsonResponse({"ok": False, "error": "Payment session expired. Please start a new order."})

        order = _create_order_from_pending(pending, rzp_payment_id)

    cart = _get_or_create_cart(request.user)
    cart.items.all().delete()
    request.session.pop(_SESSION_COUPON, None)

    return JsonResponse({"ok": True, "redirect": f"/orders/{order.order_id}"})


@require_POST
@login_required
def razorpay_payment_failed(request):
    """Log a cancellation or failure from the Razorpay modal (client-side signal)."""
    data = _body(request)
    rzp_order_id = data.get("razorpay_order_id", "")
    reason = (data.get("reason", "") or "User cancelled")[:500]

    if rzp_order_id:
        PaymentAttempt.objects.filter(
            razorpay_order_id=rzp_order_id,
            user=request.user,
            status=PaymentAttemptStatus.INITIATED,
        ).update(status=PaymentAttemptStatus.CANCELLED, failure_reason=reason)
        RazorpayPendingOrder.objects.filter(
            razorpay_order_id=rzp_order_id,
            user=request.user,
            status=PendingOrderStatus.PENDING,
        ).update(status=PendingOrderStatus.FAILED)

    return JsonResponse({"ok": True})


@require_POST
def razorpay_webhook(request):
    """
    Server-side Razorpay webhook. Belt-and-suspenders: handles payment.captured
    when the browser crashes after payment but before verify-payment is called,
    and logs payment.failed events server-side.
    """
    import hashlib
    import hmac as _hmac
    from django.db import transaction as _tx

    webhook_secret = ""
    try:
        from .models import IntegrationConfig
        rows = {r.key: r.value for r in IntegrationConfig.objects.filter(integration="RAZORPAY")}
        webhook_secret = rows.get("webhook_secret", "")
    except Exception:
        pass
    if not webhook_secret:
        webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")

    if webhook_secret:
        received_sig = request.META.get("HTTP_X_RAZORPAY_SIGNATURE", "")
        expected_sig = _hmac.new(
            webhook_secret.encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not _hmac.compare_digest(expected_sig, received_sig):
            return HttpResponse(status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except ValueError:
        return HttpResponse(status=400)

    event          = payload.get("event", "")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    rzp_order_id   = payment_entity.get("order_id", "")
    rzp_payment_id = payment_entity.get("id", "")

    if event == "payment.captured" and rzp_order_id:
        with _tx.atomic():
            pending = RazorpayPendingOrder.objects.select_for_update().filter(
                razorpay_order_id=rzp_order_id,
                status=PendingOrderStatus.PENDING,
            ).first()
            if pending and not pending.is_expired():
                _create_order_from_pending(pending, rzp_payment_id)

    elif event == "payment.failed" and rzp_order_id:
        RazorpayPendingOrder.objects.filter(
            razorpay_order_id=rzp_order_id,
            status=PendingOrderStatus.PENDING,
        ).update(status=PendingOrderStatus.FAILED)
        PaymentAttempt.objects.filter(
            razorpay_order_id=rzp_order_id,
            status=PaymentAttemptStatus.INITIATED,
        ).update(
            status=PaymentAttemptStatus.FAILED,
            failure_reason=payment_entity.get("error_description", "Payment failed")[:500],
        )

    return HttpResponse(status=200)


@require_POST
@login_required
def address_update(request, pk):
    data = _body(request)
    try:
        addr = request.user.addresses.get(pk=pk)
    except UserAddress.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Address not found."})

    street_flat = (data.get("street_flat") or "").strip()
    address = (data.get("address") or "").strip()
    city = (data.get("city") or "").strip()
    pin_code = (data.get("pin_code") or "").strip()

    if not (address and city and pin_code):
        return JsonResponse({"ok": False, "error": "Address, city, and pincode are required."})

    addr.address_name = (data.get("address_name") or "Home").strip()
    addr.street_flat = street_flat
    addr.address = address
    addr.city = city
    addr.pin_code = pin_code
    addr.landmark = (data.get("landmark") or "").strip()

    if data.get("is_default"):
        request.user.addresses.exclude(pk=pk).update(is_default=False)
        addr.is_default = True

    addr.save()
    return JsonResponse({"ok": True})


# --------------------------------------------------------------------------- #
# Reviews
# --------------------------------------------------------------------------- #
def _notify(user, title, message):
    Notification.objects.create(user=user, title=title, message=message)


@require_POST
@login_required
def review_create(request):
    product = get_object_or_404(Product, id=request.POST.get("productId"))
    redirect_url = f"/product/{product.slug}"
    try:
        rating = max(1, min(5, int(request.POST.get("rating", 5))))
    except (TypeError, ValueError):
        rating = 5
    title   = request.POST.get("title", "").strip()[:200]
    comment = request.POST.get("comment", "").strip()
    is_anonymous = request.POST.get("is_anonymous") == "on"

    if not comment:
        messages.error(request, "Please write a review.")
        return redirect(redirect_url)

    purchased = OrderItem.objects.filter(
        product=product, order__user=request.user,
        order__status=OrderStatus.DELIVERED
    ).exists()
    if not purchased:
        messages.error(request, "You can only review products from delivered orders.")
        return redirect(redirect_url)
    if Review.objects.filter(user=request.user, product=product).exists():
        messages.error(request, "You've already reviewed this product.")
        return redirect(redirect_url)

    review = Review.objects.create(
        user=request.user, product=product,
        rating=rating, title=title, comment=comment,
        status=ReviewStatus.PENDING, is_verified=True,
        is_anonymous=is_anonymous,
    )

    # Upload images to Cloudinary
    from core.cloudinary_storage import upload_file as cl_upload
    upload_errors = []
    for f in request.FILES.getlist("images")[:4]:
        data = f.read()
        url, err = cl_upload(data, f.name, f.content_type)
        if url:
            ReviewImage.objects.create(review=review, image_url=url)
        elif err:
            upload_errors.append(err)
    if upload_errors:
        messages.warning(request, f"Review submitted, but image upload failed: {upload_errors[0]}")
    else:
        messages.success(request, "Thanks! Your review has been submitted and is pending approval.")
    return redirect(redirect_url)


@login_required
def review_edit(request, pk):
    review = get_object_or_404(Review, pk=pk, user=request.user)
    if not review.can_edit:
        messages.error(request, "Reviews can only be edited within 24 hours of submission.")
        return redirect("/my-reviews")

    if request.method == "POST":
        try:
            rating = max(1, min(5, int(request.POST.get("rating", review.rating))))
        except (TypeError, ValueError):
            rating = review.rating
        title   = request.POST.get("title", "").strip()[:200]
        comment = request.POST.get("comment", "").strip()
        is_anonymous = request.POST.get("is_anonymous") == "on"
        if not comment:
            messages.error(request, "Review text cannot be empty.")
            return redirect(f"/my-reviews")

        review.rating = rating
        review.title  = title
        review.comment = comment
        review.is_anonymous = is_anonymous
        review.status = ReviewStatus.PENDING  # re-submit for approval
        from django.utils import timezone as _tz
        review.edited_at = _tz.now()
        review.save(update_fields=["rating", "title", "comment", "is_anonymous", "status", "edited_at"])

        # Replace images if new ones uploaded
        new_files = request.FILES.getlist("images")
        if new_files:
            review.images.all().delete()
            from core.cloudinary_storage import upload_file as cl_upload
            upload_errors = []
            for f in new_files[:4]:
                data = f.read()
                url, err = cl_upload(data, f.name, f.content_type)
                if url:
                    ReviewImage.objects.create(review=review, image_url=url)
                elif err:
                    upload_errors.append(err)
            if upload_errors:
                messages.warning(request, f"Review updated, but image upload failed: {upload_errors[0]}")
            else:
                messages.success(request, "Review updated and resubmitted for approval.")
        else:
            messages.success(request, "Review updated and resubmitted for approval.")
        return redirect("/my-reviews")

    return render(request, "site/review_edit.html", {"review": review})


@require_POST
@login_required
def review_delete_customer(request, pk):
    review = get_object_or_404(Review, pk=pk, user=request.user)
    if not review.can_edit:
        messages.error(request, "Reviews can only be deleted within 24 hours of submission.")
        return redirect("/my-reviews")
    review.delete()
    messages.success(request, "Review deleted.")
    return redirect("/my-reviews")


@login_required
def my_reviews(request):
    from django.utils import timezone
    reviews = (request.user.reviews
               .select_related("product")
               .prefetch_related("images")
               .order_by("-created_at"))
    now = timezone.now()
    return render(request, "site/my_reviews.html", {
        "reviews": reviews,
        "now": now,
    })


# --------------------------------------------------------------------------- #
# Account — comprehensive profile management hub
# --------------------------------------------------------------------------- #
@login_required
def account(request):
    u = request.user
    from accounts.models import ActivityLog, LoginHistory, ActivityType
    from django.db.models import Sum

    orders = u.orders.all()
    order_count = orders.count()
    total_spent = orders.filter(
        payment_status=PaymentStatus.PAID
    ).aggregate(total=Sum("grand_total"))["total"] or 0

    fav_count = u.favourites.count()
    review_count = Review.objects.filter(user=u).count()
    notif_unread = u.notifications.filter(is_read=False).count()

    # Customer classification
    paid_orders = orders.filter(payment_status=PaymentStatus.PAID).count()
    if paid_orders >= 10 or float(total_spent) >= 10000:
        classification = "VIP"
    elif paid_orders >= 3:
        classification = "Repeat"
    else:
        classification = "New"

    activity = ActivityLog.objects.filter(user=u).select_related()[:20]
    login_hist = LoginHistory.objects.filter(user=u)[:10]

    return render(request, "site/account.html", {
        "addresses":       u.addresses.all(),
        "order_count":     order_count,
        "fav_count":       fav_count,
        "review_count":    review_count,
        "notif_unread":    notif_unread,
        "total_spent":     total_spent,
        "classification":  classification,
        "activity":        activity,
        "login_history":   login_hist,
        "activity_types":  ActivityType,
    })


@login_required
def notifications(request):
    items = request.user.notifications.all()
    items.filter(is_read=False).update(is_read=True)
    return render(request, "site/notifications.html", {"items": items})


# --------------------------------------------------------------------------- #
# Content pages
# --------------------------------------------------------------------------- #
def blogs(request):
    items = Blog.objects.filter(status=Status.ACTIVE).order_by("-created_at")
    return render(request, "site/blogs.html", {"blogs": items})


def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug, status=Status.ACTIVE)
    more = Blog.objects.filter(status=Status.ACTIVE).exclude(id=blog.id).order_by("-created_at")[:3]
    return render(request, "site/blog_detail.html", {"blog": blog, "more": more})


def faq(request):
    q = request.GET.get("q", "").strip()
    if q:
        items = Faq.objects.filter(status=Status.ACTIVE).filter(
            Q(question__icontains=q) | Q(answer__icontains=q)
        ).order_by("position")
        return render(request, "site/faq.html", {"faqs": items, "q": q, "cats": [], "uncategorised": []})
    cats = FaqCategory.objects.filter(is_active=True).prefetch_related(
        Prefetch("items",
                 queryset=Faq.objects.filter(status=Status.ACTIVE).order_by("position"),
                 to_attr="active_items")
    )
    uncategorised = Faq.objects.filter(status=Status.ACTIVE, category__isnull=True).order_by("position")
    return render(request, "site/faq.html", {"cats": cats, "uncategorised": uncategorised, "q": "", "faqs": []})


def testimonials(request):
    items = Testimonial.objects.filter(approval_status=ReviewStatus.APPROVED).order_by("-is_featured", "position", "-created_at")
    return render(request, "site/testimonials.html", {"testimonials": items})


@login_required(login_url="/login")
def submit_testimonial(request):
    user = request.user
    my_testimonials = Testimonial.objects.filter(user=user).order_by("-created_at")
    submitted_count  = my_testimonials.count()
    approved_count   = my_testimonials.filter(approval_status=ReviewStatus.APPROVED).count()
    user_orders = Order.objects.filter(user=user, payment_status=PaymentStatus.PAID).order_by("-created_at")[:20]

    if request.method == "POST":
        name    = request.POST.get("name", "").strip()
        email   = request.POST.get("email", "").strip()
        order_id = request.POST.get("order_id", "").strip()
        rating  = int(request.POST.get("rating", 5))
        title   = request.POST.get("title", "").strip()
        comment = request.POST.get("comment", "").strip()
        city    = request.POST.get("city", "").strip()
        consent = bool(request.POST.get("consent"))
        edit_pk = request.POST.get("edit_pk", "").strip()

        if not name or not comment or not consent:
            messages.error(request, "Name, testimonial message, and consent are required.")
            return redirect("/submit-testimonial")

        rating = max(1, min(5, rating))
        photo_url = None
        if request.FILES.get("photo"):
            try:
                import cloudinary.uploader
                result = cloudinary.uploader.upload(
                    request.FILES["photo"],
                    folder="spicearog/testimonials",
                    transformation=[{"width": 300, "height": 300, "crop": "fill", "gravity": "face"}],
                )
                photo_url = result["secure_url"]
            except Exception:
                pass

        order_obj = None
        if order_id:
            try:
                order_obj = Order.objects.get(pk=order_id, user=user)
            except Order.DoesNotExist:
                pass

        if edit_pk:
            try:
                t = Testimonial.objects.get(pk=edit_pk, user=user, approval_status=ReviewStatus.PENDING)
                t.name    = name
                t.email   = email
                t.order   = order_obj
                t.rating  = rating
                t.title   = title
                t.comment = comment
                t.city    = city
                t.consent = consent
                if photo_url:
                    t.image = photo_url
                t.save()
                messages.success(request, "Your testimonial has been updated and is awaiting review.")
            except Testimonial.DoesNotExist:
                messages.error(request, "Testimonial not found or cannot be edited.")
        else:
            Testimonial.objects.create(
                user=user, name=name, email=email, order=order_obj,
                rating=rating, title=title, comment=comment, city=city,
                consent=consent, image=photo_url,
                approval_status=ReviewStatus.PENDING,
                status=Status.INACTIVE,
            )
            messages.success(request, "Thank you! Your testimonial has been submitted and is awaiting review.")
        return redirect("/submit-testimonial")

    return render(request, "site/submit_testimonial.html", {
        "my_testimonials": my_testimonials,
        "submitted_count": submitted_count,
        "approved_count":  approved_count,
        "user_orders":     user_orders,
    })


@login_required(login_url="/login")
def delete_testimonial(request, pk):
    if request.method == "POST":
        t = get_object_or_404(Testimonial, pk=pk, user=request.user)
        if t.approval_status == ReviewStatus.PENDING:
            t.delete()
            messages.success(request, "Testimonial deleted.")
        else:
            messages.error(request, "Only pending testimonials can be deleted.")
    return redirect("/submit-testimonial")


def _policy(request, ptype, fallback):
    policy = Policy.objects.filter(type=ptype).first()
    title = policy.title if policy else fallback
    content = policy.content if policy else "<p>Content coming soon.</p>"
    return render(request, "site/policy.html", {"title": title, "content": content, "page": policy})


def about(request):
    policy = Policy.objects.filter(type=PolicyType.ABOUT_US).first()
    team   = TeamMember.objects.filter(is_active=True).order_by("position")
    return render(request, "site/about.html", {
        "policy":  policy,
        "content": policy.content if policy else "",
        "team":    team,
    })


def terms(request):
    return _policy(request, PolicyType.TERMS, "Terms & Conditions")


def privacy(request):
    return _policy(request, PolicyType.PRIVACY, "Privacy Policy")


def shipping_policy(request):
    return _policy(request, PolicyType.SHIPPING, "Shipping Policy")


def returns_policy(request):
    return _policy(request, PolicyType.RETURNS, "Return & Refund Policy")


def help_support(request):
    contact_page = Policy.objects.filter(type=PolicyType.CONTACT).first()
    if request.method == "POST":
        Enquiry.objects.create(
            user=request.user if request.user.is_authenticated else None,
            name=request.POST.get("name", ""),
            email=request.POST.get("email", ""),
            mobile=request.POST.get("mobile", ""),
            subject=request.POST.get("subject", ""),
            message=request.POST.get("message", ""),
        )
        messages.success(request, "Thanks — we'll get back to you shortly.")
        return redirect("/help-support")
    return render(request, "site/help_support.html", {"contact_page": contact_page})


# --------------------------------------------------------------------------- #
# Profile Management APIs
# --------------------------------------------------------------------------- #

def _json_ok(**kwargs):
    return JsonResponse({"ok": True, **kwargs})

def _json_err(msg, status=400):
    return JsonResponse({"ok": False, "error": msg}, status=status)

def _send_otp_sms(mobile, otp_code):
    """
    Send OTP via SMS gateway configured in IntegrationConfig → SMS.
    Returns (True, message) or (False, error_string).
    `mobile` should be the raw value stored on the user (10-digit or with +91).
    """
    try:
        from store.models import IntegrationConfig
        if IntegrationConfig.get("SMS", "enabled", "false") != "true":
            return False, "SMS integration not enabled."
        provider    = IntegrationConfig.get("SMS", "provider", "")
        api_key     = IntegrationConfig.get("SMS", "api_key", "")
        account_sid = IntegrationConfig.get("SMS", "account_sid", "")
        sender_id   = IntegrationConfig.get("SMS", "sender_id", "")
        if not provider or not api_key:
            return False, "SMS provider or API key not configured."

        import requests as _req

        if provider == "fast2sms":
            # Strip country prefix — Fast2SMS expects plain 10-digit number
            num = mobile.lstrip("+")
            if num.startswith("91") and len(num) == 12:
                num = num[2:]
            resp = _req.get(
                "https://www.fast2sms.com/dev/bulkV2",
                params={"authorization": api_key, "route": "otp",
                        "variables_values": str(otp_code), "flash": 0, "numbers": num},
                headers={"cache-control": "no-cache"},
                timeout=10,
            )
            data = resp.json()
            if data.get("return"):
                return True, "OTP sent via Fast2SMS."
            msg = data.get("message", "Fast2SMS error")
            return False, (msg[0] if isinstance(msg, list) else str(msg))

        elif provider == "msg91":
            # MSG91 OTP API — needs country code prefix
            num = mobile.lstrip("+")
            if not num.startswith("91"):
                num = "91" + num.lstrip("0")
            resp = _req.post(
                "https://api.msg91.com/api/v5/otp",
                json={"template_id": sender_id, "mobile": num,
                      "authkey": api_key, "otp": str(otp_code)},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            data = resp.json()
            if data.get("type") == "success":
                return True, "OTP sent via MSG91."
            return False, data.get("message", "MSG91 error")

        elif provider == "twilio":
            if not account_sid or not sender_id:
                return False, "Twilio Account SID and From number required."
            to_num   = mobile if mobile.startswith("+") else f"+91{mobile.lstrip('0')}"
            from_num = sender_id if sender_id.startswith("+") else f"+{sender_id}"
            import base64
            creds = base64.b64encode(f"{account_sid}:{api_key}".encode()).decode()
            resp = _req.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                data={"From": from_num, "To": to_num,
                      "Body": f"Your OTP is {otp_code}. Valid for 10 minutes. Do not share."},
                headers={"Authorization": f"Basic {creds}"},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return True, "OTP sent via Twilio."
            return False, resp.json().get("message", "Twilio error")

        return False, f"Unknown SMS provider: {provider}"
    except Exception as e:
        return False, f"SMS send error: {e}"


def _send_otp_email(to_address, user, otp_obj):
    """
    Send OTP via SMTP configured in IntegrationConfig → EMAIL.
    Returns True on success, False if SMTP is not configured or send fails.
    For email-change OTPs, caller must pass the NEW email as to_address.
    """
    try:
        from store.models import IntegrationConfig
        if IntegrationConfig.get("EMAIL", "enabled", "false") != "true":
            return False
        host       = IntegrationConfig.get("EMAIL", "host", "")
        port       = int(IntegrationConfig.get("EMAIL", "port", "587") or "587")
        username   = IntegrationConfig.get("EMAIL", "username", "")
        password   = IntegrationConfig.get("EMAIL", "password", "")
        use_tls    = IntegrationConfig.get("EMAIL", "use_tls", "true") == "true"
        from_email = IntegrationConfig.get("EMAIL", "from_email", "") or username
        if not host or not username or not from_email:
            return False
        from django.core.mail import get_connection, EmailMessage
        conn = get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=host, port=port, username=username, password=password,
            use_tls=use_tls, fail_silently=False,
        )
        subject = "Your Spicearog Verification Code"
        body = (
            f"Hi {user.full_name or 'there'},\n\n"
            f"Your verification code is: {otp_obj.code}\n\n"
            f"This code expires in 10 minutes. Do not share it with anyone.\n\n"
            f"— Spicearog Team"
        )
        EmailMessage(subject, body, from_email, [to_address], connection=conn).send()
        return True
    except Exception:
        return False


@login_required
@require_POST
def profile_update(request):
    u = request.user
    from accounts.models import ActivityLog, ActivityType

    u.first_name = request.POST.get("first_name", u.first_name or "").strip() or None
    u.last_name  = request.POST.get("last_name",  u.last_name or "").strip() or None
    u.city       = request.POST.get("city",        u.city or "").strip() or None
    dob = request.POST.get("date_of_birth", "").strip()
    if dob:
        try:
            from datetime import date
            u.date_of_birth = date.fromisoformat(dob)
        except ValueError:
            return _json_err("Invalid date of birth format.")
    gender = request.POST.get("gender", "").strip()
    if gender:
        from accounts.models import Gender
        if gender in [g.value for g in Gender]:
            u.gender = gender
    u.save(update_fields=["first_name", "last_name", "city", "date_of_birth", "gender", "updated_at"])
    ActivityLog.log(u, ActivityType.PROFILE_UPDATED, "Updated personal information")
    return _json_ok(message="Profile updated successfully.")


@login_required
@require_POST
def profile_photo_upload(request):
    from accounts.models import ActivityLog, ActivityType
    f = request.FILES.get("photo")
    if not f:
        return _json_err("No file provided.")
    if f.size > 5 * 1024 * 1024:
        return _json_err("File size must be under 5 MB.")
    if not f.content_type.startswith("image/"):
        return _json_err("Only image files are allowed.")

    from core.cloudinary_storage import upload_file
    url, err = upload_file(f.read(), f.name, f.content_type)
    if err:
        return _json_err(f"Upload failed: {err}")

    u = request.user
    u.profile_image_url = url
    u.save(update_fields=["profile_image_url", "updated_at"])
    ActivityLog.log(u, ActivityType.PHOTO_UPDATED, "Updated profile photo")
    return _json_ok(url=url, message="Profile photo updated.")


@login_required
@require_POST
def email_change_request(request):
    from accounts.models import OTPRequest, OTPType, User
    new_email = request.POST.get("new_email", "").strip().lower()
    if not new_email:
        return _json_err("New email is required.")
    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
        return _json_err("This email is already in use.")
    otp = OTPRequest.create_for(request.user, OTPType.EMAIL_CHANGE, new_value=new_email)
    sent = _send_otp_email(new_email, request.user, otp)
    if sent:
        return _json_ok(message=f"Verification code sent to {new_email}. Check your inbox.")
    return _json_ok(
        message=f"SMTP not configured. Dev code: {otp.code}",
        dev_code=otp.code,
    )


@login_required
@require_POST
def email_change_verify(request):
    from accounts.models import OTPRequest, OTPType, ActivityLog, ActivityType, User
    code = request.POST.get("code", "").strip()
    otp = OTPRequest.objects.filter(
        user=request.user, otp_type=OTPType.EMAIL_CHANGE, is_used=False
    ).order_by("-created_at").first()
    if not otp or not otp.is_valid():
        return _json_err("OTP has expired or is invalid. Please request a new one.")
    if otp.code != code:
        return _json_err("Incorrect verification code.")

    new_email = otp.new_value
    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return _json_err("This email is now taken by another account.")

    old_email = request.user.email
    request.user.email = new_email
    request.user.save(update_fields=["email", "updated_at"])
    otp.is_used = True
    otp.save(update_fields=["is_used"])
    ActivityLog.log(request.user, ActivityType.EMAIL_CHANGED,
                    f"Changed email from {old_email} to {new_email}")
    return _json_ok(message="Email address updated successfully.")


@login_required
@require_POST
def phone_change_request(request):
    from accounts.models import OTPRequest, OTPType, User
    new_phone = request.POST.get("new_phone", "").strip()
    if not new_phone:
        return _json_err("New phone number is required.")
    if User.objects.filter(mobile=new_phone).exclude(pk=request.user.pk).exists():
        return _json_err("This phone number is already registered.")
    otp = OTPRequest.create_for(request.user, OTPType.PHONE_CHANGE, new_value=new_phone)
    sent, err = _send_otp_sms(new_phone, otp.code)
    if sent:
        return _json_ok(message=f"A 6-digit OTP has been sent to {new_phone}.")
    # SMS not configured — surface code in dev, hide in production
    from django.conf import settings as _s
    if getattr(_s, "DEBUG", False):
        return _json_ok(message=f"[Dev] OTP: {otp.code} (SMS not configured: {err})")
    return _json_ok(message=f"A verification code has been sent to {new_phone}.")


@login_required
@require_POST
def phone_change_verify(request):
    from accounts.models import OTPRequest, OTPType, ActivityLog, ActivityType, User
    code = request.POST.get("code", "").strip()
    otp = OTPRequest.objects.filter(
        user=request.user, otp_type=OTPType.PHONE_CHANGE, is_used=False
    ).order_by("-created_at").first()
    if not otp or not otp.is_valid():
        return _json_err("OTP has expired or is invalid.")
    if otp.code != code:
        return _json_err("Incorrect verification code.")

    new_phone = otp.new_value
    if User.objects.filter(mobile=new_phone).exclude(pk=request.user.pk).exists():
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return _json_err("This number is now taken by another account.")

    old_phone = request.user.mobile
    request.user.mobile = new_phone
    request.user.save(update_fields=["mobile", "updated_at"])
    otp.is_used = True
    otp.save(update_fields=["is_used"])
    ActivityLog.log(request.user, ActivityType.PHONE_CHANGED,
                    f"Changed phone from {old_phone} to {new_phone}")
    return _json_ok(message="Phone number updated successfully.")


@login_required
@require_POST
def password_change_view(request):
    from accounts.models import ActivityLog, ActivityType
    from django.contrib.auth.hashers import check_password
    current = request.POST.get("current_password", "")
    new1    = request.POST.get("new_password", "")
    new2    = request.POST.get("confirm_password", "")

    if not request.user.check_password(current):
        return _json_err("Current password is incorrect.")
    if len(new1) < 6:
        return _json_err("New password must be at least 6 characters.")
    if new1 != new2:
        return _json_err("New passwords do not match.")
    if check_password(new1, request.user.password):
        return _json_err("New password must be different from your current password.")

    request.user.set_password(new1)
    request.user.save(update_fields=["password", "updated_at"])
    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, request.user)
    ActivityLog.log(request.user, ActivityType.PASSWORD_CHANGED, "Changed account password")
    return _json_ok(message="Password changed successfully.")


@login_required
@require_POST
def address_add(request):
    from accounts.models import UserAddress, ActivityLog, ActivityType, AddressType
    data = request.POST
    line1 = data.get("address", "").strip()
    city  = data.get("city", "").strip()
    pin   = data.get("pin_code", "").strip()

    if not line1 or not city or not pin:
        return _json_err("Address, city, and pin code are required.")

    addr_type = data.get("address_type", AddressType.HOME)
    if addr_type not in [a.value for a in AddressType]:
        addr_type = AddressType.HOME

    is_default = data.get("is_default") in ("1", "true", "True", True)
    if is_default:
        request.user.addresses.update(is_default=False)

    addr = UserAddress.objects.create(
        user=request.user,
        address_type=addr_type,
        address_name=data.get("address_name", "").strip() or None,
        recipient_name=data.get("recipient_name", "").strip() or None,
        phone=data.get("phone", "").strip() or None,
        address=line1,
        street_flat=data.get("street_flat", "").strip() or None,
        landmark=data.get("landmark", "").strip() or None,
        city=city,
        state=data.get("state", "").strip() or None,
        pin_code=pin,
        is_default=is_default or not request.user.addresses.filter(is_default=True).exists(),
    )
    ActivityLog.log(request.user, ActivityType.ADDRESS_ADDED,
                    f"Added {addr.get_address_type_display()} address in {city}")
    return _json_ok(id=addr.pk, message="Address saved successfully.")


@login_required
@require_POST
def address_edit(request, pk):
    from accounts.models import UserAddress, ActivityLog, ActivityType, AddressType
    addr = get_object_or_404(UserAddress, pk=pk, user=request.user)
    data = request.POST

    line1 = data.get("address", "").strip()
    city  = data.get("city", "").strip()
    pin   = data.get("pin_code", "").strip()

    if not line1 or not city or not pin:
        return _json_err("Address, city, and pin code are required.")

    addr_type = data.get("address_type", addr.address_type)
    if addr_type not in [a.value for a in AddressType]:
        addr_type = addr.address_type

    is_default = data.get("is_default") in ("1", "true", "True", True)
    if is_default:
        request.user.addresses.exclude(pk=pk).update(is_default=False)

    addr.address_type  = addr_type
    addr.address_name  = data.get("address_name", "").strip() or None
    addr.recipient_name = data.get("recipient_name", "").strip() or None
    addr.phone         = data.get("phone", "").strip() or None
    addr.address       = line1
    addr.street_flat   = data.get("street_flat", "").strip() or None
    addr.landmark      = data.get("landmark", "").strip() or None
    addr.city          = city
    addr.state         = data.get("state", "").strip() or None
    addr.pin_code      = pin
    addr.is_default    = is_default
    addr.save()

    ActivityLog.log(request.user, ActivityType.ADDRESS_UPDATED,
                    f"Updated {addr.get_address_type_display()} address in {city}")
    return _json_ok(message="Address updated successfully.")


@login_required
@require_POST
def address_delete(request, pk):
    from accounts.models import UserAddress, ActivityLog, ActivityType
    addr = get_object_or_404(UserAddress, pk=pk, user=request.user)
    was_default = addr.is_default
    city = addr.city
    addr_type = addr.get_address_type_display()
    addr.delete()
    if was_default:
        first = request.user.addresses.first()
        if first:
            first.is_default = True
            first.save(update_fields=["is_default"])
    ActivityLog.log(request.user, ActivityType.ADDRESS_DELETED,
                    f"Deleted {addr_type} address in {city}")
    return _json_ok(message="Address deleted.")


@login_required
@require_POST
def address_set_default(request, pk):
    addr = get_object_or_404(UserAddress, pk=pk, user=request.user)
    request.user.addresses.update(is_default=False)
    addr.is_default = True
    addr.save(update_fields=["is_default"])
    return _json_ok(message="Default address updated.")


@login_required
@require_POST
def notification_prefs_update(request):
    from accounts.models import ActivityLog, ActivityType
    u = request.user
    u.notif_email = request.POST.get("notif_email") in ("1", "true", "on", "True")
    u.notif_sms   = request.POST.get("notif_sms")   in ("1", "true", "on", "True")
    u.notif_push  = request.POST.get("notif_push")  in ("1", "true", "on", "True")
    u.save(update_fields=["notif_email", "notif_sms", "notif_push", "updated_at"])
    ActivityLog.log(u, ActivityType.NOTIF_PREFS, "Updated notification preferences")
    return _json_ok(message="Notification preferences saved.")


@login_required
@require_POST
def logout_all_sessions(request):
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    from accounts.models import ActivityLog, ActivityType

    current_session_key = request.session.session_key
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        data = session.get_decoded()
        if data.get("_auth_user_id") == str(request.user.pk):
            if session.session_key != current_session_key:
                session.delete()
    ActivityLog.log(request.user, ActivityType.LOGOUT, "Logged out from all other devices")
    return _json_ok(message="All other sessions have been signed out.")


@login_required
@require_POST
def delete_account_request(request):
    from accounts.models import OTPRequest, OTPType
    otp = OTPRequest.create_for(request.user, OTPType.DELETE_ACCOUNT, ttl_minutes=10)
    sent = _send_otp_email(request.user.email, request.user, otp)
    if sent:
        return _json_ok(message="A verification code has been sent to your email address.")
    return _json_ok(
        message=f"SMTP not configured. Dev code: {otp.code}",
        dev_code=otp.code,
    )


@login_required
@require_POST
def delete_account_confirm(request):
    from accounts.models import OTPRequest, OTPType, Status, ActivityLog, ActivityType
    from django.contrib.auth import logout as auth_logout
    code = request.POST.get("code", "").strip()
    otp = OTPRequest.objects.filter(
        user=request.user, otp_type=OTPType.DELETE_ACCOUNT, is_used=False
    ).order_by("-created_at").first()
    if not otp or not otp.is_valid():
        return _json_err("Verification code has expired. Please request a new one.")
    if otp.code != code:
        return _json_err("Incorrect verification code.")

    otp.is_used = True
    otp.save(update_fields=["is_used"])

    u = request.user
    u.status = Status.INACTIVE
    u.email = f"deleted_{u.pk}_{u.email or u.mobile}"
    u.mobile = None
    u.save(update_fields=["status", "email", "mobile", "updated_at"])
    auth_logout(request)
    return _json_ok(redirect="/", message="Your account has been deactivated.")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or \
        request.content_type == "application/json"


def _body(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST
