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
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Status
from core.utils import gen_code
from .models import (
    Banner, BannerType, Blog, Cart, CartItem, Category, Enquiry, Favourite,
    Order, OrderItem, PaymentMode, PaymentStatus, Policy, PolicyType, Product,
    ProductVariant, Review, Testimonial, Faq, OrderStatus,
)


# --------------------------------------------------------------------------- #
# Home / landing page  (port of (site)/page.tsx + api/home)
# --------------------------------------------------------------------------- #
def home(request):
    banner = (Banner.objects.filter(type=BannerType.HOME_BANNER, status=Status.ACTIVE)
              .order_by("position").first())
    categories = Category.objects.filter(status=Status.ACTIVE).order_by("position")[:5]
    products = (Product.objects.filter(status=Status.ACTIVE, is_featured=True)
                .order_by("position")[:settings.HOME_PRODUCT_LIMIT])
    brand_videos = Banner.objects.filter(type=BannerType.BRAND, status=Status.ACTIVE).order_by("position")
    blogs = Blog.objects.filter(status=Status.ACTIVE).order_by("-created_at")[:settings.HOME_BLOG_LIMIT]
    testimonials = (Testimonial.objects.filter(status=Status.ACTIVE)
                    .order_by("position")[:settings.HOME_TESTIMONIAL_LIMIT])
    fav_ids = _fav_ids(request.user)
    return render(request, "site/home.html", {
        "banner": banner, "categories": categories, "products": products,
        "brand_videos": brand_videos, "blogs": list(blogs)[:3], "testimonials": testimonials,
        "fav_ids": fav_ids,
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
def products(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    qs = Product.objects.filter(status=Status.ACTIVE).select_related("category").order_by("position")
    if q:
        qs = qs.filter(name__icontains=q)
    if category:
        qs = qs.filter(category__slug=category)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page", 1))
    return render(request, "site/products.html", {
        "page_obj": page, "q": q, "active_category": category,
        "categories": Category.objects.filter(status=Status.ACTIVE).order_by("position"),
        "fav_ids": _fav_ids(request.user), "total": paginator.count,
    })


def categories(request):
    cats = Category.objects.filter(status=Status.ACTIVE).order_by("position")
    return render(request, "site/categories.html", {"categories": cats})


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related("variants", "images", "reviews__user"),
        slug=slug, status=Status.ACTIVE,
    )
    related = (Product.objects.filter(category=product.category, status=Status.ACTIVE)
               .exclude(id=product.id).order_by("position")[:settings.RELATED_PRODUCT_LIMIT])
    reviews = product.reviews.all().order_by("-created_at")
    can_review = False
    already_reviewed = False
    if request.user.is_authenticated:
        already_reviewed = product.reviews.filter(user=request.user).exists()
        purchased = OrderItem.objects.filter(product=product, order__user=request.user).exists()
        can_review = purchased and not already_reviewed
    return render(request, "site/product_detail.html", {
        "product": product, "variants": product.active_variants, "images": product.images.all(),
        "related": related, "reviews": reviews, "can_review": can_review,
        "already_reviewed": already_reviewed,
        "favourited": request.user.is_authenticated and
        product.favourites.filter(user=request.user).exists(),
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


@login_required
def cart_view(request):
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related("variant", "variant__product").all()
    subtotal = sum(i.line_total for i in items)
    shipping = 0 if subtotal >= settings.FREE_DELIVERY_OVER else settings.SHIPPING_FEE
    return render(request, "site/cart.html", {
        "items": items, "subtotal": subtotal, "shipping": shipping,
        "grand_total": subtotal + shipping,
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


# --------------------------------------------------------------------------- #
# Orders / checkout  (port of api/orders)
# --------------------------------------------------------------------------- #
@login_required
def orders(request):
    qs = (Order.objects.filter(user=request.user)
          .prefetch_related("items").order_by("-created_at"))
    return render(request, "site/orders.html", {"orders": qs})


@login_required
def checkout(request):
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related("variant", "variant__product").all()
    if not items:
        messages.error(request, "Your cart is empty.")
        return redirect("/cart")
    subtotal = sum(i.line_total for i in items)
    shipping = 0 if subtotal >= settings.FREE_DELIVERY_OVER else settings.SHIPPING_FEE
    grand_total = subtotal + shipping

    if request.method == "POST":
        payment_mode = request.POST.get("paymentMode", PaymentMode.COD)
        shipping_address = {
            "name": request.POST.get("name", ""),
            "mobile": request.POST.get("mobile", ""),
            "address": request.POST.get("address", ""),
            "city": request.POST.get("city", ""),
            "pinCode": request.POST.get("pinCode", ""),
        }
        order_code = gen_code("SPG")
        razorpay_order_id = None
        if payment_mode == PaymentMode.RAZORPAY:
            try:
                import razorpay
                client = razorpay.Client(
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                rzp_order = client.order.create({
                    "amount": round(grand_total * 100), "currency": "INR", "receipt": order_code})
                razorpay_order_id = rzp_order["id"]
            except Exception:
                messages.error(request, "Payment gateway not configured.")
                return redirect("/checkout")

        order = Order.objects.create(
            order_id=order_code, invoice_no=f"INV-{order_code}", user=request.user,
            sub_total=subtotal, shipping_amount=shipping, grand_total=grand_total,
            payment_mode=payment_mode, razorpay_order_id=razorpay_order_id,
            shipping_address=json.dumps(shipping_address), no_of_product=len(items),
        )
        for i in items:
            OrderItem.objects.create(
                order=order, product=i.product, variant=i.variant,
                name=i.variant.product.name, variant_label=i.variant.variant,
                price=i.price, qty=i.qty, net_total=i.line_total,
            )
        if payment_mode == PaymentMode.COD:
            cart.items.all().delete()
        messages.success(request, f"Order {order_code} placed successfully!")
        return redirect("/orders")

    default = request.user.addresses.filter(is_default=True).first() or \
        request.user.addresses.first()
    return render(request, "site/checkout.html", {
        "items": items, "subtotal": subtotal, "shipping": shipping,
        "grand_total": grand_total, "default_address": default,
    })


# --------------------------------------------------------------------------- #
# Reviews  (port of api/reviews — purchase-gated, one per user/product)
# --------------------------------------------------------------------------- #
@require_POST
@login_required
def review_create(request):
    product = get_object_or_404(Product, id=request.POST.get("productId"))
    try:
        rating = int(request.POST.get("rating", 5))
    except (TypeError, ValueError):
        rating = 5
    comment = request.POST.get("comment", "").strip()
    if not comment:
        messages.error(request, "Please write a comment.")
        return redirect(product.get_absolute_url() if hasattr(product, "get_absolute_url")
                        else f"/product/{product.slug}")
    purchased = OrderItem.objects.filter(product=product, order__user=request.user).exists()
    if not purchased:
        messages.error(request, "You can review only products you've purchased.")
        return redirect(f"/product/{product.slug}")
    if Review.objects.filter(user=request.user, product=product).exists():
        messages.error(request, "You've already reviewed this product.")
        return redirect(f"/product/{product.slug}")
    Review.objects.create(user=request.user, product=product, rating=rating, comment=comment)
    messages.success(request, "Thanks for your review!")
    return redirect(f"/product/{product.slug}")


# --------------------------------------------------------------------------- #
# Account
# --------------------------------------------------------------------------- #
@login_required
def account(request):
    if request.method == "POST":
        u = request.user
        u.first_name = request.POST.get("first_name", u.first_name)
        u.last_name = request.POST.get("last_name", u.last_name)
        u.mobile = request.POST.get("mobile", u.mobile) or None
        u.city = request.POST.get("city", u.city)
        u.save()
        messages.success(request, "Profile updated.")
        return redirect("/account")
    return render(request, "site/account.html", {
        "addresses": request.user.addresses.all(),
        "order_count": request.user.orders.count(),
        "fav_count": request.user.favourites.count(),
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
    items = Faq.objects.filter(status=Status.ACTIVE).order_by("position")
    return render(request, "site/faq.html", {"faqs": items})


def testimonials(request):
    items = Testimonial.objects.filter(status=Status.ACTIVE).order_by("position")
    return render(request, "site/testimonials.html", {"testimonials": items})


def _policy(request, ptype, fallback):
    policy = Policy.objects.filter(type=ptype).first()
    title = policy.title if policy else fallback
    content = policy.content if policy else "<p>Content coming soon.</p>"
    return render(request, "site/policy.html", {"title": title, "content": content})


def about(request):
    return _policy(request, PolicyType.ABOUT_US, "About Us")


def terms(request):
    return _policy(request, PolicyType.TERMS, "Terms & Conditions")


def privacy(request):
    return _policy(request, PolicyType.PRIVACY, "Privacy Policy")


def help_support(request):
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
    return render(request, "site/help_support.html")


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
