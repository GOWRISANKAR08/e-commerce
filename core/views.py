"""
Custom admin panel — the rich dashboard (faithful port of api/admin/stats +
admin/(dash)/page.tsx) plus management list pages for the catalog and orders.
Long-tail sections (banners, blogs, testimonials, faq, policies, enquiries,
reviews, users, offers) are managed through the built-in Django admin, linked
from the sidebar.
"""
import calendar
import csv
from datetime import datetime
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User, UserType, Status
from core.nav import ADMIN_NAV
from core.utils import gen_code, slugify
from store.models import (
    Banner, BannerType, Category, ComboImage, ComboItem, ComboPackage,
    Coupon, CouponType, Enquiry, EnquiryStatus, Order, OrderChannel,
    OrderItem, OrderStatus, OrderRefund, PaymentStatus, Product, ProductVariant,
    Review, ReviewStatus, StockStatus, StockThreshold, StockStatusHistory,
)

# --------------------------------------------------------------------------- #
# Order workflow engine
# --------------------------------------------------------------------------- #
# Fixed progression — cannot skip or reverse.
ORDER_WORKFLOW = [
    OrderStatus.PROCESSING,
    OrderStatus.ORDER_CONFIRMED,
    OrderStatus.PACKED,
    OrderStatus.DISPATCHED,
    OrderStatus.DELIVERED,
]

# Valid next states from each status (including cancellation paths).
WORKFLOW_TRANSITIONS: dict[str, list[str]] = {
    OrderStatus.PROCESSING:     [OrderStatus.ORDER_CONFIRMED, OrderStatus.CANCELLED],
    OrderStatus.ORDER_CONFIRMED:[OrderStatus.PACKED,          OrderStatus.CANCELLED],
    OrderStatus.PACKED:         [OrderStatus.DISPATCHED,      OrderStatus.CANCELLED],
    OrderStatus.DISPATCHED:     [OrderStatus.DELIVERED,       OrderStatus.CANCELLED],
    OrderStatus.DELIVERED:      [OrderStatus.REFUNDED],
    OrderStatus.CANCELLED:      [],
    OrderStatus.REFUNDED:       [],
}

# Statuses where stock has already been deducted (confirmed or beyond).
STOCK_DEDUCTED_STATUSES = {
    OrderStatus.ORDER_CONFIRMED,
    OrderStatus.PACKED,
    OrderStatus.DISPATCHED,
    OrderStatus.DELIVERED,
}


def _valid_transition(from_status: str, to_status: str) -> bool:
    return to_status in WORKFLOW_TRANSITIONS.get(from_status, [])


def _deduct_stock_for_order(order: Order) -> None:
    """
    Deduct stock for every item in *order* (called on ORDER_CONFIRMED).
    Uses SELECT FOR UPDATE to be safe under concurrent requests.
    Prevents stock from going negative and auto-computes new status via thresholds.
    """
    with transaction.atomic():
        for item in order.items.select_related("variant__product").all():
            v = ProductVariant.objects.select_for_update().get(pk=item.variant_id)
            old_stock, old_status = v.stock, v.stock_status

            deducted = min(item.qty, v.stock)        # never below 0
            v.stock = max(v.stock - item.qty, 0)
            v.reserved_stock = v.reserved_stock + deducted

            threshold = StockThreshold.get_for_product(v.product)
            v.stock_status = threshold.compute_status(v.stock)
            v.save(update_fields=["stock", "reserved_stock", "stock_status"])

            if old_stock != v.stock or old_status != v.stock_status:
                StockStatusHistory.objects.create(
                    variant=v, old_status=old_status, new_status=v.stock_status,
                    old_stock=old_stock, new_stock=v.stock,
                    note=f"Order {order.order_id} confirmed",
                )


def _restore_stock_for_order(order: Order) -> None:
    """
    Restore reserved stock back to available stock (called on CANCELLED).
    Only acts when the order is in a state where stock was already deducted.
    """
    if order.status not in STOCK_DEDUCTED_STATUSES:
        return
    with transaction.atomic():
        for item in order.items.select_related("variant__product").all():
            v = ProductVariant.objects.select_for_update().get(pk=item.variant_id)
            old_stock, old_status = v.stock, v.stock_status

            restored = min(item.qty, v.reserved_stock)
            v.stock = v.stock + restored
            v.reserved_stock = max(v.reserved_stock - restored, 0)

            threshold = StockThreshold.get_for_product(v.product)
            v.stock_status = threshold.compute_status(v.stock)
            v.save(update_fields=["stock", "reserved_stock", "stock_status"])

            StockStatusHistory.objects.create(
                variant=v, old_status=old_status, new_status=v.stock_status,
                old_stock=old_stock, new_stock=v.stock,
                note=f"Order {order.order_id} cancelled — stock restored",
            )


def _release_reserved_on_deliver(order: Order) -> None:
    """
    Clear reserved_stock when an order is DELIVERED (goods have left the warehouse).
    Available stock is unchanged — it was already deducted at confirmation.
    """
    with transaction.atomic():
        for item in order.items.select_related("variant").all():
            v = ProductVariant.objects.select_for_update().get(pk=item.variant_id)
            v.reserved_stock = max(v.reserved_stock - item.qty, 0)
            v.save(update_fields=["reserved_stock"])


def admin_required(view):
    @wraps(view)
    @login_required(login_url="/admin-login")
    def wrapper(request, *args, **kwargs):
        if request.user.user_type != UserType.ADMIN:
            return redirect("/admin-login")
        return view(request, *args, **kwargs)
    return wrapper


def _ctx(active, **extra):
    base = {"ADMIN_NAV": ADMIN_NAV, "active_path": active}
    base.update(extra)
    return base


# --------------------------------------------------------------------------- #
# Dashboard — full stats port
# --------------------------------------------------------------------------- #
@admin_required
def dashboard(request):
    now = timezone.now()

    products = Product.objects.filter(status=Status.ACTIVE).count()
    orders = Order.objects.count()
    users = User.objects.filter(user_type=UserType.USER).count()
    reviews = Review.objects.count()
    enquiries = Enquiry.objects.filter(status=EnquiryStatus.OPEN).count()

    revenue = (Order.objects.filter(payment_status=PaymentStatus.PAID)
               .aggregate(s=Sum("grand_total"))["s"] or 0)
    avg_order = (Order.objects.filter(payment_status=PaymentStatus.PAID)
                 .aggregate(a=Avg("grand_total"))["a"] or 0)

    pipeline = {
        "pending": Order.objects.filter(status=OrderStatus.PROCESSING).count(),
        "confirmed": Order.objects.filter(status=OrderStatus.ORDER_CONFIRMED).count(),
        "packed": Order.objects.filter(status=OrderStatus.PACKED).count(),
        "dispatched": Order.objects.filter(status=OrderStatus.DISPATCHED).count(),
        "delivered": Order.objects.filter(status=OrderStatus.DELIVERED).count(),
        "returns": Order.objects.filter(
            status__in=[OrderStatus.CANCELLED, OrderStatus.REFUNDED]).count(),
    }

    _active_v = ProductVariant.objects.filter(product__status=Status.ACTIVE, status=Status.ACTIVE)
    inv = {
        "inStock":    _active_v.filter(stock_status=StockStatus.IN_STOCK).count(),
        "lowStock":   _active_v.filter(stock_status=StockStatus.LOW_STOCK).count(),
        "outOfStock": _active_v.filter(stock_status=StockStatus.OUT_OF_STOCK).count(),
        "total":      _active_v.count(),
    }
    inv["expiring"] = 0
    health_pct = round(inv["inStock"] / inv["total"] * 100) if inv["total"] else 0
    low_share = round(inv["lowStock"] / inv["total"] * 100) if inv["total"] else 0
    out_share = round(inv["outOfStock"] / inv["total"] * 100) if inv["total"] else 0

    recent_orders = (Order.objects.select_related("user")
                     .prefetch_related("items").order_by("-created_at")[:6])

    # 12-month revenue
    monthly = []
    for i in range(12):
        m = now.month - 11 + i
        y = now.year + (m - 1) // 12
        mm = (m - 1) % 12 + 1
        start = now.replace(year=y, month=mm, day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(y, mm)[1]
        end = start.replace(day=last_day, hour=23, minute=59, second=59)
        rev = (Order.objects.filter(payment_status=PaymentStatus.PAID,
                                    created_at__gte=start, created_at__lte=end)
               .aggregate(s=Sum("grand_total"))["s"] or 0)
        monthly.append({"month": calendar.month_abbr[mm], "revenue": rev})

    max_rev = max([m["revenue"] for m in monthly] + [1])
    for m in monthly:
        m["pct"] = max(round(m["revenue"] / max_rev * 100), 4)
    avg_monthly = sum(m["revenue"] for m in monthly) / len(monthly) if monthly else 0
    best_month = max(monthly, key=lambda m: m["revenue"]) if monthly else None

    # top products by revenue
    top_items = (OrderItem.objects.values("product_id")
                 .annotate(revenue=Sum("net_total"), qty=Sum("qty"))
                 .order_by("-revenue")[:5])
    pid_map = {p.id: p for p in Product.objects.filter(
        id__in=[t["product_id"] for t in top_items]).select_related("category")}
    top_max = max([t["revenue"] or 0 for t in top_items] + [1])
    top_products = []
    for t in top_items:
        p = pid_map.get(t["product_id"])
        top_products.append({
            "product": p, "revenue": t["revenue"] or 0, "qty": t["qty"] or 0,
            "bar_pct": round((t["revenue"] or 0) / top_max * 100),
            "in_stock": (p.variants.first().stock_status != StockStatus.OUT_OF_STOCK
                         if p and p.variants.exists() else True),
        })

    low_stock_items = (_active_v.select_related("product")
                       .filter(stock_status__in=[StockStatus.LOW_STOCK, StockStatus.OUT_OF_STOCK])
                       .order_by("stock")[:4])

    # Inventory analytics for dashboard — active products/variants only
    inv_analytics = {
        "total_skus":  _active_v.count(),
        "in_stock":    _active_v.filter(stock_status=StockStatus.IN_STOCK).count(),
        "low_stock":   _active_v.filter(stock_status=StockStatus.LOW_STOCK).count(),
        "out_stock":   _active_v.filter(stock_status=StockStatus.OUT_OF_STOCK).count(),
        "reserved":    (_active_v.aggregate(r=Sum("reserved_stock"))["r"] or 0),
        "total_stock": (_active_v.aggregate(s=Sum("stock"))["s"] or 0),
    }

    stat_cards = [
        {"label": "Total Revenue", "value": revenue, "kind": "money", "icon": "rupee",
         "color": "#16a34a", "bg": "#f0fdf4", "growth": "+12.4% this month", "up": True},
        {"label": "Total Orders", "value": orders, "kind": "num", "icon": "bag",
         "color": "#ea580c", "bg": "#fff7ed", "growth": "+8.1% this month", "up": True},
        {"label": "Customers", "value": users, "kind": "num", "icon": "users",
         "color": "#0ea5e9", "bg": "#f0f9ff", "growth": "+18.2% this month", "up": True},
        {"label": "Products", "value": products, "kind": "num", "icon": "package",
         "color": "#16a34a", "bg": "#f0fdf4", "growth": "10 added this month", "up": True},
        {"label": "Conversion Rate", "value": "5.6%", "kind": "raw", "icon": "percent",
         "color": "#6b7280", "bg": "#f3f4f6", "growth": "+0.4% this month", "up": True},
        {"label": "Avg Order Value", "value": round(avg_order), "kind": "money", "icon": "trend",
         "color": "#6b7280", "bg": "#f3f4f6", "growth": "-2.1% this month", "up": False},
    ]

    pipeline_stages = [
        {"label": "Pending", "count": pipeline["pending"], "icon": "clock", "color": "#f59e0b"},
        {"label": "Confirmed", "count": pipeline["confirmed"], "icon": "check", "color": "#22c55e"},
        {"label": "Packed", "count": pipeline["packed"], "icon": "package", "color": "#3b82f6"},
        {"label": "Shipped", "count": pipeline["dispatched"], "icon": "truck", "color": "#8b5cf6"},
        {"label": "Delivered", "count": pipeline["delivered"], "icon": "check", "color": "#10b981"},
        {"label": "Returns", "count": pipeline["returns"], "icon": "refresh", "color": "#ef4444"},
    ]

    hour = timezone.localtime(now).hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

    return render(request, "panel/dashboard.html", _ctx(
        "/admin-panel",
        greeting=greeting,
        first_name=(request.user.first_name or "Admin"),
        today=timezone.localtime(now).strftime("%d %B %Y"),
        stat_cards=stat_cards, monthly=monthly,
        total_revenue=revenue, avg_monthly=avg_monthly, best_month=best_month,
        recent_orders=recent_orders, pipeline_stages=pipeline_stages,
        inv=inv, health_pct=health_pct, low_share=low_share, out_share=out_share,
        low_stock_items=low_stock_items, top_products=top_products,
        inv_analytics=inv_analytics,
    ))


# --------------------------------------------------------------------------- #
# Catalog management
# --------------------------------------------------------------------------- #
@admin_required
def products_list(request):
    q = request.GET.get("q", "").strip()
    cat_filter = request.GET.get("cat", "").strip()
    status_filter = request.GET.get("status", "").strip()
    sort = request.GET.get("sort", "position").strip()
    page_num = request.GET.get("page", 1)
    show_archived = request.GET.get("show", "") == "archived"

    back_url = "/admin-panel/products?show=archived" if show_archived else "/admin-panel/products"

    # ── Bulk POST actions ────────────────────────────────────────────
    if request.method == "POST":
        action = request.POST.get("bulk_action", "")
        ids = request.POST.getlist("product_ids")
        if ids and action:
            if show_archived:
                # Archived mode: IDs are Product PKs
                if action == "restore":
                    Product.objects.filter(pk__in=ids).update(status=Status.ACTIVE)
                    messages.success(request, f"Restored {len(ids)} product(s).")
                elif action == "delete":
                    Product.objects.filter(pk__in=ids).delete()
                    messages.success(request, f"Permanently deleted {len(ids)} product(s).")
            else:
                # Active mode: IDs are ProductVariant PKs
                if action == "delete":
                    ProductVariant.objects.filter(pk__in=ids).delete()
                    messages.success(request, f"Deleted {len(ids)} SKU(s).")
                elif action == "archive":
                    # Archive the parent product so it shows up in the Archived tab
                    product_ids = (ProductVariant.objects.filter(pk__in=ids)
                                   .values_list("product_id", flat=True).distinct())
                    Product.objects.filter(pk__in=product_ids).update(status=Status.INACTIVE)
                    messages.success(request, f"Archived {len(ids)} SKU(s).")
                elif action == "duplicate":
                    for vid in ids:
                        try:
                            v = ProductVariant.objects.get(pk=vid)
                            v.pk = None
                            v.va_code = gen_code("SKU")
                            v.variant = f"{v.variant} (Copy)"
                            v.reserved_stock = 0
                            v.save()
                        except ProductVariant.DoesNotExist:
                            pass
                    messages.success(request, f"Duplicated {len(ids)} SKU(s).")
        return redirect(back_url)

    # ── Stat cards: mutually exclusive, sum to total, no archived ───
    stat_base = ProductVariant.objects.filter(
        product__status=Status.ACTIVE, status=Status.ACTIVE
    )
    total_products = stat_base.count()
    in_stock  = stat_base.filter(stock_status=StockStatus.IN_STOCK).count()
    low_stock = stat_base.filter(stock_status=StockStatus.LOW_STOCK).count()
    out_stock = stat_base.filter(stock_status=StockStatus.OUT_OF_STOCK).count()
    cat_count  = Category.objects.count()
    avg_rating = round(
        Review.objects.filter(status="APPROVED").aggregate(a=Avg("rating"))["a"] or 0, 1
    )
    archived_count = Product.objects.filter(status=Status.INACTIVE).count()

    # ── Queryset ─────────────────────────────────────────────────────
    if show_archived:
        # Product-level view for archived tab
        qs = (Product.objects
              .filter(status=Status.INACTIVE)
              .select_related("category")
              .prefetch_related("variants", "reviews")
              .order_by("-updated_at"))
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    else:
        # Variant-as-product: one row per active variant of active products
        qs = (stat_base
              .select_related("product", "product__category")
              .prefetch_related("product__reviews"))
        if q:
            qs = qs.filter(
                Q(product__name__icontains=q) | Q(va_code__icontains=q) | Q(variant__icontains=q)
            )
        if cat_filter:
            qs = qs.filter(product__category__slug=cat_filter)
        if status_filter:
            qs = qs.filter(stock_status=status_filter)
        sort_map = {
            "name":      "product__name",
            "date_desc": "-product__created_at",
            "date_asc":  "product__created_at",
        }
        qs = qs.order_by(sort_map.get(sort, "product__position"))

    filtered_total = qs.count()
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(page_num)

    return render(request, "panel/products.html", _ctx(
        "/admin-panel/products",
        products=page_obj, page_obj=page_obj,
        q=q, cat_filter=cat_filter, status_filter=status_filter, sort=sort,
        total=total_products, filtered_total=filtered_total,
        in_stock=in_stock, low_stock=low_stock, out_stock=out_stock,
        cat_count=cat_count, avg_rating=avg_rating,
        categories=Category.objects.order_by("position"),
        stock_statuses=StockStatus.choices,
        show_archived=show_archived,
        archived_count=archived_count,
    ))


@admin_required
def product_clone(request, pk):
    if request.method != "POST":
        return redirect("/admin-panel/products")
    orig = get_object_or_404(Product, pk=pk)
    orig.pk = None
    orig.code = gen_code("PRD")
    orig.name = f"{orig.name} (Copy)"
    orig.slug = slugify(orig.name)
    orig.save()
    messages.success(request, f"Cloned successfully.")
    return redirect("/admin-panel/products")


@admin_required
def product_export(request):
    q = request.GET.get("q", "").strip()
    cat_filter = request.GET.get("cat", "").strip()
    status_filter = request.GET.get("status", "").strip()
    ids = request.GET.getlist("ids")

    qs = (Product.objects.filter(status=Status.ACTIVE)
          .select_related("category")
          .prefetch_related("variants", "reviews").order_by("position"))
    if ids:
        qs = qs.filter(pk__in=ids)
    else:
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        if cat_filter:
            qs = qs.filter(category__slug=cat_filter)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="products_export.csv"'
    response.write("﻿")  # BOM for Excel UTF-8

    writer = csv.writer(response)
    writer.writerow(["Code (SKU)", "Name", "Category", "MRP (₹)", "Price (₹)",
                     "Stock", "Stock Status", "Product Status", "Avg Rating", "Created"])
    for p in qs:
        v = p.default_variant
        total_stock = sum(pv.stock for pv in p.variants.all())
        writer.writerow([
            p.code, p.name, p.category.name,
            f"{v.mrp_price:.2f}" if v else "",
            f"{v.selling_price:.2f}" if v else "",
            total_stock,
            v.get_stock_status_display() if v else "",
            p.get_status_display(),
            p.avg_rating,
            p.created_at.strftime("%d %b %Y"),
        ])
    return response


@admin_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        data = dict(
            name=name,
            slug=request.POST.get("slug") or slugify(name),
            description=request.POST.get("description", ""),
            image=request.POST.get("image", "") or "/seed/placeholder.jpg",
            badge=request.POST.get("badge") or None,
            youtube_link=request.POST.get("youtube_link") or None,
            is_featured=bool(request.POST.get("is_featured")),
            top_seller=bool(request.POST.get("top_seller")),
            status=request.POST.get("status", Status.ACTIVE),
            position=int(request.POST.get("position") or 1),
            category=get_object_or_404(Category, pk=request.POST.get("category")),
        )
        if product:
            for k, v in data.items():
                setattr(product, k, v)
            product.save()
            messages.success(request, "Product updated.")
        else:
            data["code"] = gen_code("PRD")
            product = Product.objects.create(**data)
            messages.success(request, "Product created.")
        return redirect("/admin-panel/products")
    return render(request, "panel/product_form.html", _ctx(
        "/admin-panel/products", product=product,
        categories=Category.objects.order_by("position"),
        statuses=Status.choices))


@admin_required
def product_delete(request, pk):
    Product.objects.filter(pk=pk).delete()
    messages.success(request, "Product deleted.")
    return redirect("/admin-panel/products")


@admin_required
def categories_list(request):
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    sort = request.GET.get("sort", "position").strip()

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        pk = request.POST.get("pk", "").strip()
        data = dict(
            name=name,
            slug=request.POST.get("slug") or slugify(name),
            description=request.POST.get("description", "").strip(),
            image=request.POST.get("image") or None,
            position=int(request.POST.get("position") or 1),
            status=request.POST.get("status", Status.ACTIVE),
        )
        if pk:
            cat = get_object_or_404(Category, pk=pk)
            for k, v in data.items():
                setattr(cat, k, v)
            cat.save()
            messages.success(request, f'Category "{name}" updated.')
        else:
            data["code"] = request.POST.get("code") or gen_code("CAT")
            Category.objects.create(**data)
            messages.success(request, f'Category "{name}" added.')
        return redirect("/admin-panel/categories")

    all_cats = Category.objects.annotate(n=Count("products"))
    total_cats = all_cats.count()
    active_count = all_cats.filter(status=Status.ACTIVE).count()
    inactive_count = all_cats.filter(status=Status.INACTIVE).count()
    total_products = Product.objects.filter(status=Status.ACTIVE).count()

    cats = all_cats
    if q:
        cats = cats.filter(Q(name__icontains=q) | Q(slug__icontains=q) | Q(code__icontains=q))
    if status_filter:
        cats = cats.filter(status=status_filter)
    sort_map = {
        "name":     "name",
        "products": "-n",
        "date":     "-created_at",
        "position": "position",
    }
    cats = cats.order_by(sort_map.get(sort, "position"))

    return render(request, "panel/categories.html", _ctx(
        "/admin-panel/categories",
        categories=cats, statuses=Status.choices,
        active_count=active_count, inactive_count=inactive_count,
        total_products=total_products, total_cats=total_cats,
        q=q, status_filter=status_filter, sort=sort,
    ))


@admin_required
def category_delete(request, pk):
    Category.objects.filter(pk=pk).delete()
    messages.success(request, "Category deleted.")
    return redirect("/admin-panel/categories")


@admin_required
def category_export(request):
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    cats = Category.objects.annotate(n=Count("products"))
    if q:
        cats = cats.filter(Q(name__icontains=q) | Q(slug__icontains=q) | Q(code__icontains=q))
    if status_filter:
        cats = cats.filter(status=status_filter)
    cats = cats.order_by("position")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="categories_export.csv"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(["Code", "Name", "Description", "Slug", "Position", "Status", "Products", "Created"])
    for c in cats:
        writer.writerow([
            c.code, c.name, c.description, c.slug, c.position,
            c.get_status_display(), c.n, c.created_at.strftime("%d %b %Y"),
        ])
    return response


@admin_required
def variants_list(request):
    if request.method == "POST":
        product = get_object_or_404(Product, pk=request.POST.get("product"))
        ProductVariant.objects.create(
            product=product, va_code=request.POST.get("va_code") or gen_code("VA"),
            variant=request.POST.get("variant", ""),
            short_name=request.POST.get("short_name") or request.POST.get("variant", ""),
            selling_price=float(request.POST.get("selling_price") or 0),
            mrp_price=float(request.POST.get("mrp_price") or 0),
            stock=int(request.POST.get("stock") or 0),
            position=int(request.POST.get("position") or 1))
        messages.success(request, "Variant added.")
        return redirect("/admin-panel/variants")
    all_variants = (ProductVariant.objects
                    .select_related("product", "product__category")
                    .order_by("product__name", "position"))
    total_v = all_variants.count()
    in_stock_v = all_variants.filter(stock_status=StockStatus.IN_STOCK).count()
    low_stock_v = all_variants.filter(stock_status=StockStatus.LOW_STOCK).count()
    out_stock_v = all_variants.filter(stock_status=StockStatus.OUT_OF_STOCK).count()
    # Group by product
    from itertools import groupby
    grouped = []
    for product, group in groupby(all_variants, key=lambda v: v.product_id):
        variants_list_g = list(group)
        grouped.append({"product": variants_list_g[0].product, "variants": variants_list_g})
    return render(request, "panel/variants.html", _ctx(
        "/admin-panel/variants",
        grouped=grouped, products=Product.objects.order_by("name"),
        total_v=total_v, in_stock_v=in_stock_v, low_stock_v=low_stock_v, out_stock_v=out_stock_v))


@admin_required
def variant_delete(request, pk):
    v = get_object_or_404(ProductVariant, pk=pk)
    redirect_url = "/admin-panel/products" if request.GET.get("from") == "products" else "/admin-panel/variants"
    v.delete()
    messages.success(request, "Variant deleted.")
    return redirect(redirect_url)


@admin_required
def variant_clone(request, pk):
    if request.method != "POST":
        return redirect("/admin-panel/products")
    v = get_object_or_404(ProductVariant, pk=pk)
    v.pk = None
    v.va_code = gen_code("SKU")
    v.variant = f"{v.variant} (Copy)"
    v.reserved_stock = 0
    v.save()
    messages.success(request, f'Variant cloned as "{v.variant}".')
    return redirect("/admin-panel/products")


@admin_required
def inventory(request):
    if request.method == "POST":
        action = request.POST.get("action", "save_stock")

        # ── Save / update global threshold ──────────────────────────────────
        if action == "save_threshold":
            in_min = max(int(request.POST.get("in_stock_min") or 51), 1)
            low_min = max(int(request.POST.get("low_stock_min") or 1), 0)
            if low_min >= in_min:
                messages.error(request, "Low Stock threshold must be less than In Stock threshold.")
                return redirect("/admin-panel/inventory")
            try:
                t = StockThreshold.objects.get(product__isnull=True)
                t.in_stock_min = in_min
                t.low_stock_min = low_min
                t.save()
            except StockThreshold.DoesNotExist:
                StockThreshold.objects.create(product=None, in_stock_min=in_min, low_stock_min=low_min)
            messages.success(request, f"Threshold updated: ≥{in_min} In Stock · ≥{low_min} Low Stock.")
            return redirect("/admin-panel/inventory")

        # ── Apply threshold rules to all variants in bulk ────────────────────
        if action == "apply_thresholds":
            updated = 0
            for v in ProductVariant.objects.select_related("product").all():
                threshold = StockThreshold.get_for_product(v.product)
                new_status = threshold.compute_status(v.stock)
                if v.stock_status != new_status:
                    old_status = v.stock_status
                    v.stock_status = new_status
                    v.save(update_fields=["stock_status"])
                    StockStatusHistory.objects.create(
                        variant=v,
                        old_status=old_status,
                        new_status=new_status,
                        old_stock=v.stock,
                        new_stock=v.stock,
                        note="Bulk threshold apply",
                    )
                    updated += 1
            messages.success(request, f"Rules applied — {updated} variant{'s' if updated != 1 else ''} updated.")
            return redirect("/admin-panel/inventory")

        # ── Save individual variant stock (auto-compute status) ──────────────
        v = get_object_or_404(ProductVariant, pk=request.POST.get("variant_id"))
        old_stock = v.stock
        old_status = v.stock_status
        new_stock = max(int(request.POST.get("stock") or 0), 0)

        threshold = StockThreshold.get_for_product(v.product)
        new_status = threshold.compute_status(new_stock)

        v.stock = new_stock
        v.stock_status = new_status
        v.save()

        if old_stock != new_stock or old_status != new_status:
            StockStatusHistory.objects.create(
                variant=v,
                old_status=old_status,
                new_status=new_status,
                old_stock=old_stock,
                new_stock=new_stock,
            )

        messages.success(
            request,
            f"{v.product.name} ({v.variant}): {new_stock} units → {v.get_stock_status_display()}",
        )
        return redirect("/admin-panel/inventory")

    # ── GET ──────────────────────────────────────────────────────────────────
    now = timezone.now()
    thirty_days_ago = now - timezone.timedelta(days=30)
    variants = (ProductVariant.objects
                .select_related("product", "product__category")
                .order_by("stock_status", "stock"))
    total_skus = variants.count()
    in_stock_c = variants.filter(stock_status=StockStatus.IN_STOCK).count()
    low_stock_c = variants.filter(stock_status=StockStatus.LOW_STOCK).count()
    out_stock_c = variants.filter(stock_status=StockStatus.OUT_OF_STOCK).count()

    sold_map = {
        r["variant_id"]: r["sold"]
        for r in (OrderItem.objects
                  .filter(order__created_at__gte=thirty_days_ago)
                  .values("variant_id")
                  .annotate(sold=Sum("qty")))
    }

    # Last history entry per variant — cross-database via Max(id) trick
    from django.db.models import Max as _Max
    latest_ids = list(
        StockStatusHistory.objects.values("variant_id").annotate(mid=_Max("id")).values_list("mid", flat=True)
    )
    last_history_map = {
        h.variant_id: h
        for h in StockStatusHistory.objects.filter(id__in=latest_ids)
    }

    variants_data = []
    max_stock = max((v.stock for v in variants), default=1) or 1
    for v in variants:
        variants_data.append({
            "variant": v,
            "sold_30d": sold_map.get(v.id, 0),
            "stock_pct": min(round(v.stock / max_stock * 100), 100),
            "last_history": last_history_map.get(v.id),
        })

    health_pct = round(in_stock_c / total_skus * 100) if total_skus else 0
    low_share = round(low_stock_c / total_skus * 100) if total_skus else 0
    out_share = round(out_stock_c / total_skus * 100) if total_skus else 0
    alert_items = [r for r in variants_data if r["variant"].stock_status in (
        StockStatus.LOW_STOCK, StockStatus.OUT_OF_STOCK)][:6]

    # Global threshold (used for JS preview too)
    try:
        global_threshold = StockThreshold.objects.get(product__isnull=True)
    except StockThreshold.DoesNotExist:
        global_threshold = StockThreshold(in_stock_min=51, low_stock_min=1)

    # Recent history (last 10 changes, all variants)
    recent_history = StockStatusHistory.objects.select_related("variant__product").order_by("-changed_at")[:10]

    total_reserved = (variants.aggregate(r=Sum("reserved_stock"))["r"] or 0)

    return render(request, "panel/inventory.html", _ctx(
        "/admin-panel/inventory",
        variants_data=variants_data,
        total_skus=total_skus, in_stock_c=in_stock_c, low_stock_c=low_stock_c,
        out_stock_c=out_stock_c, total_reserved=total_reserved,
        health_pct=health_pct, low_share=low_share,
        out_share=out_share, alert_items=alert_items,
        global_threshold=global_threshold,
        recent_history=recent_history,
    ))


# --------------------------------------------------------------------------- #
# Orders management
# --------------------------------------------------------------------------- #
TAB_STATUS_MAP = {
    "pending": [OrderStatus.PROCESSING],
    "processing": [OrderStatus.ORDER_CONFIRMED, OrderStatus.PACKED],
    "shipped": [OrderStatus.DISPATCHED],
    "delivered": [OrderStatus.DELIVERED],
    "cancelled": [OrderStatus.CANCELLED],
    "returns": [OrderStatus.REFUNDED],
}

TAB_LABELS = {
    "": "All",
    "pending": "Pending",
    "processing": "Processing",
    "shipped": "Shipped",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
    "returns": "Returns",
}


@admin_required
def orders_list(request):
    from django.db.models import Q
    tab = request.GET.get("tab", "")
    q = request.GET.get("q", "").strip()
    channel = request.GET.get("channel", "")

    qs = (Order.objects.select_related("user")
          .prefetch_related("items__product").order_by("-created_at"))

    if tab and tab in TAB_STATUS_MAP:
        qs = qs.filter(status__in=TAB_STATUS_MAP[tab])
    elif request.GET.get("status"):
        qs = qs.filter(status=request.GET.get("status"))

    if q:
        qs = qs.filter(Q(order_id__icontains=q) | Q(user__first_name__icontains=q) |
                       Q(user__last_name__icontains=q) | Q(user__email__icontains=q))
    if channel:
        qs = qs.filter(channel=channel)

    # Tab counts
    tab_counts = {
        "": Order.objects.count(),
        "pending": Order.objects.filter(status__in=TAB_STATUS_MAP["pending"]).count(),
        "processing": Order.objects.filter(status__in=TAB_STATUS_MAP["processing"]).count(),
        "shipped": Order.objects.filter(status__in=TAB_STATUS_MAP["shipped"]).count(),
        "delivered": Order.objects.filter(status__in=TAB_STATUS_MAP["delivered"]).count(),
        "cancelled": Order.objects.filter(status__in=TAB_STATUS_MAP["cancelled"]).count(),
        "returns": Order.objects.filter(status__in=TAB_STATUS_MAP["returns"]).count(),
    }
    # Stat cards for header
    stat_cards = [
        {"label": "Total Orders", "value": tab_counts[""], "sub": "+8.1% this month", "up": True, "icon": "bag", "color": "#ea580c", "bg": "#fff7ed"},
        {"label": "Pending", "value": tab_counts["pending"], "sub": "Awaiting confirmation", "up": None, "icon": "clock", "color": "#f59e0b", "bg": "#fffbeb"},
        {"label": "Processing", "value": tab_counts["processing"], "sub": "Being packed", "up": None, "icon": "loader", "color": "#3b82f6", "bg": "#eff6ff"},
        {"label": "Shipped", "value": tab_counts["shipped"], "sub": "Out for delivery", "up": None, "icon": "truck", "color": "#8b5cf6", "bg": "#f5f3ff"},
        {"label": "Delivered", "value": tab_counts["delivered"], "sub": f"{round(tab_counts['delivered']/tab_counts[''] * 100, 1) if tab_counts[''] else 0}% of all orders", "up": True, "icon": "check-circle", "color": "#16a34a", "bg": "#f0fdf4"},
        {"label": "Cancelled / Returns", "value": tab_counts["cancelled"] + tab_counts["returns"], "sub": f"{round((tab_counts['cancelled']+tab_counts['returns'])/tab_counts[''] * 100, 1) if tab_counts[''] else 0}% rate", "up": False, "icon": "x-circle", "color": "#dc2626", "bg": "#fef2f2"},
    ]
    import json
    return render(request, "panel/orders.html", _ctx(
        "/admin-panel/orders", orders=qs, tab=tab, q=q, channel=channel,
        tab_counts=tab_counts, stat_cards=stat_cards, tab_labels=TAB_LABELS,
        channels=OrderChannel.choices,
        order_statuses=OrderStatus.choices, payment_statuses=PaymentStatus.choices,
        workflow_json=json.dumps(WORKFLOW_TRANSITIONS),
        cancellable_statuses=list(WORKFLOW_TRANSITIONS.keys())[:-2],  # all except CANCELLED/REFUNDED
        refundable_statuses=[OrderStatus.DELIVERED, OrderStatus.CANCELLED],
    ))


@admin_required
def order_update(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method != "POST":
        return redirect("/admin-panel/orders")

    new_status = request.POST.get("status", order.status)
    new_payment = request.POST.get("payment_status", order.payment_status)

    # Validate workflow transition (allow no-op)
    if new_status != order.status and not _valid_transition(order.status, new_status):
        messages.error(
            request,
            f"Invalid transition: {order.get_status_display()} → {new_status}. "
            f"Follow the fixed workflow.",
        )
        return redirect("/admin-panel/orders")

    # Stock side-effects
    if new_status != order.status:
        if new_status == OrderStatus.ORDER_CONFIRMED:
            _deduct_stock_for_order(order)
        elif new_status == OrderStatus.DELIVERED:
            _release_reserved_on_deliver(order)

    order.status = new_status
    order.payment_status = new_payment
    order.save()
    messages.success(request, f"Order {order.order_id} → {order.get_status_display()}.")
    return redirect("/admin-panel/orders")


@admin_required
def order_cancel(request, pk):
    """Cancel an order and restore stock if it was already deducted."""
    order = get_object_or_404(Order, pk=pk)
    if request.method != "POST":
        return redirect("/admin-panel/orders")

    if not _valid_transition(order.status, OrderStatus.CANCELLED):
        messages.error(request, f"Order {order.order_id} cannot be cancelled at this stage.")
        return redirect("/admin-panel/orders")

    _restore_stock_for_order(order)
    order.status = OrderStatus.CANCELLED
    order.save()
    messages.success(request, f"Order {order.order_id} cancelled. Stock restored.")
    return redirect("/admin-panel/orders")


@admin_required
def order_refund(request, pk):
    """Issue a full or partial refund for an order."""
    order = get_object_or_404(Order, pk=pk)
    if request.method != "POST":
        return redirect("/admin-panel/orders")

    refund_type = request.POST.get("refund_type", OrderRefund.FULL)
    try:
        amount = float(request.POST.get("amount") or order.grand_total)
    except ValueError:
        amount = order.grand_total
    amount = min(max(amount, 0), order.grand_total)
    reason = request.POST.get("reason", "").strip()

    OrderRefund.objects.create(
        order=order,
        refund_type=refund_type,
        amount=amount,
        reason=reason,
    )
    order.payment_status = PaymentStatus.REFUNDED
    if refund_type == OrderRefund.FULL:
        order.status = OrderStatus.REFUNDED
    order.save()
    from core.utils import inr
    messages.success(request, f"Refund of {inr(amount)} ({refund_type}) recorded for {order.order_id}.")
    return redirect("/admin-panel/orders")


@admin_required
def users_list(request):
    from django.db.models import Q
    q = request.GET.get("q", "").strip()
    qs = User.objects.filter(user_type=UserType.USER).order_by("-created_at")
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) |
                       Q(email__icontains=q) | Q(mobile__icontains=q))
    return render(request, "panel/users.html", _ctx("/admin-panel/users", users=qs, q=q))


@admin_required
def loyalty_members(request):
    qs = (User.objects.filter(user_type=UserType.USER)
          .annotate(order_count=Count("orders"), total_spend=Sum("orders__grand_total"))
          .order_by("-total_spend"))
    return render(request, "panel/loyalty_members.html", _ctx(
        "/admin-panel/loyalty", members=qs))


# --------------------------------------------------------------------------- #
# Analytics views
# --------------------------------------------------------------------------- #
@admin_required
def sales_reports(request):
    now = timezone.now()
    monthly = []
    for i in range(12):
        m = now.month - 11 + i
        y = now.year + (m - 1) // 12
        mm = (m - 1) % 12 + 1
        start = now.replace(year=y, month=mm, day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(y, mm)[1]
        end = start.replace(day=last_day, hour=23, minute=59, second=59)
        rev = (Order.objects.filter(payment_status=PaymentStatus.PAID,
                                    created_at__gte=start, created_at__lte=end)
               .aggregate(s=Sum("grand_total"), c=Count("id")))
        monthly.append({
            "month": calendar.month_abbr[mm],
            "month_full": start.strftime("%B"),
            "revenue": rev["s"] or 0,
            "orders": rev["c"] or 0,
        })
    max_rev = max([m["revenue"] for m in monthly] + [1])
    for m in monthly:
        m["pct"] = max(round(m["revenue"] / max_rev * 100), 4)

    total_revenue = sum(m["revenue"] for m in monthly)
    total_orders = Order.objects.filter(payment_status=PaymentStatus.PAID).count()
    avg_order = (Order.objects.filter(payment_status=PaymentStatus.PAID)
                 .aggregate(a=Avg("grand_total"))["a"] or 0)
    best_month = max(monthly, key=lambda m: m["revenue"]) if monthly else None
    avg_monthly = total_revenue / len(monthly) if monthly else 0

    # Revenue by category
    cat_revenue = (OrderItem.objects.values("product__category__name")
                   .annotate(rev=Sum("net_total"), cnt=Count("id"))
                   .order_by("-rev")[:8])
    cat_total = sum(c["rev"] or 0 for c in cat_revenue) or 1
    for c in cat_revenue:
        c["pct"] = round((c["rev"] or 0) / cat_total * 100)

    # Revenue by channel
    channel_revenue = (Order.objects.filter(payment_status=PaymentStatus.PAID)
                       .values("channel")
                       .annotate(rev=Sum("grand_total"), cnt=Count("id"))
                       .order_by("-rev"))
    ch_total = sum(c["rev"] or 0 for c in channel_revenue) or 1
    channels_display = []
    ch_colors = {"WEBSITE": "#1f6b3a", "INSTAGRAM": "#e1306c", "WHATSAPP": "#25d366", "REFERRAL": "#f2c014"}
    for c in channel_revenue:
        channels_display.append({
            "label": dict(OrderChannel.choices).get(c["channel"], c["channel"]),
            "orders": c["cnt"],
            "pct": round((c["rev"] or 0) / ch_total * 100),
            "color": ch_colors.get(c["channel"], "#6b7280"),
        })

    new_customers = User.objects.filter(user_type=UserType.USER).count()
    gross_profit = round(total_revenue * 0.35)
    returns_value = (Order.objects.filter(status=OrderStatus.REFUNDED)
                     .aggregate(s=Sum("grand_total"))["s"] or 0)

    stat_cards = [
        {"label": "Total Revenue", "value": total_revenue, "kind": "money", "growth": "+18.2% vs last year", "up": True},
        {"label": "Total Orders", "value": total_orders, "kind": "num", "growth": "+8.1% vs last year", "up": True},
        {"label": "Avg Order Value", "value": round(avg_order), "kind": "money", "growth": "-2.1% vs last year", "up": False},
        {"label": "Gross Profit", "value": gross_profit, "kind": "money", "growth": "+21.4% vs last year", "up": True},
        {"label": "Returns Value", "value": returns_value, "kind": "money", "growth": "-4.2% vs last year", "up": False},
        {"label": "New Customers", "value": new_customers, "kind": "num", "growth": "+18.2% vs last year", "up": True},
    ]
    return render(request, "panel/sales_reports.html", _ctx(
        "/admin-panel/reports",
        monthly=monthly, total_revenue=total_revenue, total_orders=total_orders,
        avg_order=round(avg_order), best_month=best_month, avg_monthly=avg_monthly,
        cat_revenue=cat_revenue, channels_display=channels_display, stat_cards=stat_cards))


@admin_required
def revenue_view(request):
    return redirect("/admin-panel/reports")


@admin_required
def performance_view(request):
    total_orders = Order.objects.count()
    delivered = Order.objects.filter(status=OrderStatus.DELIVERED).count()
    cancelled = Order.objects.filter(status__in=[OrderStatus.CANCELLED, OrderStatus.REFUNDED]).count()
    avg_order = (Order.objects.filter(payment_status=PaymentStatus.PAID)
                 .aggregate(a=Avg("grand_total"))["a"] or 0)
    total_customers = User.objects.filter(user_type=UserType.USER).count()
    total_revenue = (Order.objects.filter(payment_status=PaymentStatus.PAID)
                     .aggregate(s=Sum("grand_total"))["s"] or 0)
    conversion = round(delivered / total_orders * 100, 1) if total_orders else 0
    cancellation = round(cancelled / total_orders * 100, 1) if total_orders else 0
    top_products = (OrderItem.objects.values("product__name", "product__image")
                    .annotate(revenue=Sum("net_total"), qty=Sum("qty"))
                    .order_by("-revenue")[:5])
    return render(request, "panel/performance.html", _ctx(
        "/admin-panel/performance",
        total_orders=total_orders, delivered=delivered, cancelled=cancelled,
        conversion=conversion, cancellation=cancellation,
        avg_order=round(avg_order), total_customers=total_customers,
        total_revenue=total_revenue, top_products=top_products))


@admin_required
def admin_settings(request):
    return render(request, "panel/admin_settings.html", _ctx("/admin-panel/settings"))


# --------------------------------------------------------------------------- #
# Archive management
# --------------------------------------------------------------------------- #
@admin_required
def archived_products(request):
    if request.method == "POST":
        action = request.POST.get("bulk_action", "")
        ids = request.POST.getlist("product_ids")
        if ids:
            if action == "restore":
                Product.objects.filter(pk__in=ids).update(status=Status.ACTIVE)
                messages.success(request, f"Restored {len(ids)} product(s).")
            elif action == "delete":
                Product.objects.filter(pk__in=ids).delete()
                messages.success(request, f"Permanently deleted {len(ids)} product(s).")
        return redirect("/admin-panel/products/archived")

    q = request.GET.get("q", "").strip()
    qs = (Product.objects.filter(status=Status.INACTIVE)
          .select_related("category").prefetch_related("variants")
          .order_by("-updated_at"))
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    return render(request, "panel/archived_products.html", _ctx(
        "/admin-panel/products/archived",
        products=qs, q=q, total=qs.count(),
    ))


@admin_required
def product_restore(request, pk):
    if request.method != "POST":
        return redirect("/admin-panel/products?show=archived")
    product = get_object_or_404(Product, pk=pk)
    product.status = Status.ACTIVE
    product.save(update_fields=["status"])
    messages.success(request, f"'{product.name}' restored to active.")
    return redirect("/admin-panel/products?show=archived")


# --------------------------------------------------------------------------- #
# Product import (CSV / Excel)
# --------------------------------------------------------------------------- #
@admin_required
def product_import(request):
    if request.method == "GET":
        field_ref = [
            ("name",     "Required",  "Product name — used to match existing products"),
            ("category", "Required",  "Must match an existing category name exactly"),
            ("sku",      "Optional",  "Product code; auto-generated if blank"),
            ("variant",  "Required",  "Variant label e.g. '100g', '500ml', 'Pack of 12'"),
            ("mrp",      "Optional",  "Original / strike-through price (number)"),
            ("price",    "Required",  "Selling price (number)"),
            ("stock",    "Optional",  "Quantity in stock, default 0"),
            ("badge",    "Optional",  "Label shown on product card e.g. 'Bestseller'"),
            ("status",   "Optional",  "ACTIVE or INACTIVE (default ACTIVE)"),
        ]
        return render(request, "panel/product_import.html",
                      _ctx("/admin-panel/products/import",
                           categories=Category.objects.order_by("position"),
                           field_ref=field_ref))

    uploaded = request.FILES.get("import_file")
    if not uploaded:
        messages.error(request, "No file uploaded.")
        return redirect("/admin-panel/products/import")

    ext = uploaded.name.rsplit(".", 1)[-1].lower()
    rows = []
    errors = []

    try:
        if ext == "csv":
            import io
            content = uploaded.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
        elif ext in ("xlsx", "xls"):
            import openpyxl
            wb = openpyxl.load_workbook(uploaded, read_only=True, data_only=True)
            ws = wb.active
            headers = [str(c.value).strip().lower().replace(" ", "_") if c.value else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
            for excel_row in ws.iter_rows(min_row=2, values_only=True):
                if any(v is not None for v in excel_row):
                    rows.append(dict(zip(headers, [str(v).strip() if v is not None else "" for v in excel_row])))
        else:
            messages.error(request, "Unsupported format. Upload a .csv or .xlsx file.")
            return redirect("/admin-panel/products/import")
    except Exception as e:
        messages.error(request, f"File parse error: {e}")
        return redirect("/admin-panel/products/import")

    # Normalise header names
    def _get(row, *keys):
        for k in keys:
            if k in row:
                return (row[k] or "").strip()
        return ""

    created_p = created_v = updated_v = 0
    cat_cache = {}

    for i, row in enumerate(rows, start=2):
        name         = _get(row, "name", "product_name", "product")
        cat_name     = _get(row, "category", "category_name")
        sku          = _get(row, "sku", "code", "product_sku")
        variant_name = _get(row, "variant", "variant_name", "size")
        mrp          = _get(row, "mrp", "mrp_price", "original_price")
        price        = _get(row, "price", "selling_price", "sale_price")
        stock        = _get(row, "stock", "quantity", "qty")
        badge        = _get(row, "badge", "label")
        status_val   = _get(row, "status").upper() or Status.ACTIVE

        if not name or not cat_name or not variant_name or not price:
            errors.append(f"Row {i}: missing required fields (name, category, variant, price).")
            continue

        # Find/create category
        if cat_name not in cat_cache:
            try:
                cat_cache[cat_name] = Category.objects.get(name__iexact=cat_name)
            except Category.DoesNotExist:
                errors.append(f"Row {i}: category '{cat_name}' not found — skipped.")
                continue
        category = cat_cache[cat_name]

        # Find/create product
        try:
            mrp_f   = float(mrp or 0)
            price_f = float(price)
            stock_i = int(float(stock or 0))
        except ValueError:
            errors.append(f"Row {i}: invalid numeric value.")
            continue

        if sku:
            product, new_p = Product.objects.get_or_create(
                code=sku,
                defaults={"name": name, "slug": slugify(name),
                          "category": category, "status": status_val or Status.ACTIVE,
                          "image": "/seed/placeholder.jpg", "badge": badge or None},
            )
        else:
            product, new_p = Product.objects.get_or_create(
                name=name, category=category,
                defaults={"code": gen_code("PRD"), "slug": slugify(name),
                          "status": status_val or Status.ACTIVE,
                          "image": "/seed/placeholder.jpg", "badge": badge or None},
            )
        if new_p:
            created_p += 1

        # Find/create variant
        va_code_val = _get(row, "variant_sku", "va_code") or gen_code("SKU")
        v_qs = ProductVariant.objects.filter(product=product, variant__iexact=variant_name)
        if v_qs.exists():
            v = v_qs.first()
            v.mrp_price = mrp_f
            v.selling_price = price_f
            v.stock = stock_i
            from store.models import StockThreshold
            threshold = StockThreshold.get_for_product(product)
            v.stock_status = threshold.compute_status(stock_i)
            v.save(update_fields=["mrp_price", "selling_price", "stock", "stock_status"])
            updated_v += 1
        else:
            from store.models import StockThreshold
            threshold = StockThreshold.get_for_product(product)
            ProductVariant.objects.create(
                product=product, variant=variant_name,
                va_code=va_code_val, mrp_price=mrp_f, selling_price=price_f,
                stock=stock_i, stock_status=threshold.compute_status(stock_i),
                status=Status.ACTIVE,
            )
            created_v += 1

    msg = f"Import complete: {created_p} product(s) created, {created_v} variant(s) added, {updated_v} variant(s) updated."
    if errors:
        msg += f" {len(errors)} row(s) skipped."
        messages.warning(request, msg)
        for e in errors[:10]:
            messages.warning(request, e)
    else:
        messages.success(request, msg)
    return redirect("/admin-panel/products")


# --------------------------------------------------------------------------- #
# Media / image upload (Firebase → local fallback)
# --------------------------------------------------------------------------- #
@admin_required
def media_upload(request):
    import json as _json
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile

    if request.method != "POST":
        return HttpResponse(status=405)

    f = request.FILES.get("file")
    if not f:
        return HttpResponse(_json.dumps({"error": "No file provided"}),
                            content_type="application/json", status=400)

    # Load limits from Cloudinary config (fallback to safe defaults)
    from store.models import IntegrationConfig as _IC
    try:
        _max_mb = float(_IC.get("CLOUDINARY", "max_size_mb", "5") or "5")
    except ValueError:
        _max_mb = 5.0
    _raw_types = _IC.get("CLOUDINARY", "allowed_types", "jpg,jpeg,png,webp,gif")
    _ext_list = [t.strip().lower().lstrip(".") for t in _raw_types.split(",") if t.strip()]
    _mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                 "webp": "image/webp", "gif": "image/gif", "svg": "image/svg+xml"}
    allowed_mimes = {_mime_map.get(e, f"image/{e}") for e in _ext_list} or {
        "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}

    if f.content_type not in allowed_mimes:
        return HttpResponse(
            _json.dumps({"error": f"Only {_raw_types} images are allowed"}),
            content_type="application/json", status=400)

    if f.size > _max_mb * 1024 * 1024:
        return HttpResponse(_json.dumps({"error": f"File too large — maximum {_max_mb:.0f} MB"}),
                            content_type="application/json", status=400)

    import uuid as _uuid
    ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else "jpg"
    unique_name = f"{_uuid.uuid4().hex}.{ext}"
    file_bytes = f.read()

    # Try Cloudinary first
    from core.cloudinary_storage import upload_file as cl_upload
    url, err = cl_upload(file_bytes, unique_name, f.content_type)
    if url:
        return HttpResponse(_json.dumps({"url": url, "storage": "cloudinary"}),
                            content_type="application/json")

    # Fallback to local MEDIA_ROOT
    path = default_storage.save(f"products/{unique_name}", ContentFile(file_bytes))
    from django.conf import settings as django_settings
    url = request.build_absolute_uri(django_settings.MEDIA_URL + path)
    return HttpResponse(_json.dumps({"url": url, "storage": "local"}),
                        content_type="application/json")


# --------------------------------------------------------------------------- #
# Integrations module
# --------------------------------------------------------------------------- #
@admin_required
def integrations_view(request):
    from store.models import IntegrationConfig

    if request.method == "POST":
        integration = request.POST.get("integration", "").upper()
        if integration not in ("RAZORPAY", "CLOUDINARY"):
            messages.error(request, "Unknown integration.")
            return redirect("/admin-panel/integrations")

        # Save all posted keys for this integration
        known_keys = {
            "RAZORPAY":   ["key_id", "key_secret", "webhook_secret", "environment", "enabled"],
            "CLOUDINARY": ["cloud_name", "api_key", "api_secret", "folder", "upload_preset",
                           "max_size_mb", "allowed_types", "enabled"],
        }
        secret_keys = {"key_secret", "webhook_secret", "api_secret"}

        for key in known_keys[integration]:
            value = request.POST.get(key, "").strip()
            IntegrationConfig.set_value(
                integration=integration, key=key, value=value,
                is_secret=(key in secret_keys),
            )
        messages.success(request, f"{integration.title()} settings saved.")
        return redirect("/admin-panel/integrations")

    def cfg(integration, key, default=""):
        return IntegrationConfig.get(integration, key, default)

    ctx = {
        "rz": {
            "key_id":         cfg("RAZORPAY", "key_id"),
            "key_secret":     cfg("RAZORPAY", "key_secret"),
            "webhook_secret": cfg("RAZORPAY", "webhook_secret"),
            "environment":    cfg("RAZORPAY", "environment", "test"),
            "enabled":        cfg("RAZORPAY", "enabled", "false") == "true",
        },
        "cl": {
            "cloud_name":     cfg("CLOUDINARY", "cloud_name"),
            "api_key":        cfg("CLOUDINARY", "api_key"),
            "api_secret":     cfg("CLOUDINARY", "api_secret"),
            "folder":         cfg("CLOUDINARY", "folder", "products"),
            "upload_preset":  cfg("CLOUDINARY", "upload_preset", ""),
            "max_size_mb":    cfg("CLOUDINARY", "max_size_mb", "5"),
            "allowed_types":  cfg("CLOUDINARY", "allowed_types", "jpg,jpeg,png,webp,gif"),
            "enabled":        cfg("CLOUDINARY", "enabled", "false") == "true",
        },
    }
    return render(request, "panel/integrations.html",
                  _ctx("/admin-panel/integrations", **ctx))


@admin_required
def integration_test(request, integration):
    import json as _json
    if request.method != "POST":
        return HttpResponse(status=405)
    integration = integration.upper()

    if integration == "CLOUDINARY":
        from core.cloudinary_storage import test_connection
        ok, msg = test_connection()
    elif integration == "RAZORPAY":
        ok, msg = _test_razorpay()
    else:
        ok, msg = False, "Unknown integration."

    return HttpResponse(_json.dumps({"ok": ok, "message": msg}),
                        content_type="application/json")


def _test_razorpay():
    from store.models import IntegrationConfig
    key_id     = IntegrationConfig.get("RAZORPAY", "key_id")
    key_secret = IntegrationConfig.get("RAZORPAY", "key_secret")
    if not key_id or not key_secret:
        return False, "Razorpay Key ID and Key Secret are required."
    try:
        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))
        # A lightweight API call to verify credentials
        client.order.all({"count": 1})
        return True, f"Razorpay connection successful (environment: {IntegrationConfig.get('RAZORPAY', 'environment', 'test')})"
    except ImportError:
        return False, "razorpay package not installed."
    except Exception as e:
        err = str(e)
        if "401" in err or "authentication" in err.lower():
            return False, "Authentication failed — check your Key ID and Key Secret."
        return False, f"Connection error: {err}"


# --------------------------------------------------------------------------- #
# Combo Packs
# --------------------------------------------------------------------------- #
@admin_required
def combo_list(request):
    from django.http import JsonResponse

    if request.method == "POST":
        action = request.POST.get("action", "")
        ids = request.POST.getlist("ids")
        if ids:
            if action == "delete":
                ComboPackage.objects.filter(pk__in=ids).delete()
                messages.success(request, f"Deleted {len(ids)} combo(s).")
            elif action == "publish":
                ComboPackage.objects.filter(pk__in=ids).update(status=ComboPackage.Status.ACTIVE)
                messages.success(request, f"Published {len(ids)} combo(s).")
            elif action == "draft":
                ComboPackage.objects.filter(pk__in=ids).update(status=ComboPackage.Status.DRAFT)
                messages.success(request, f"Moved {len(ids)} combo(s) to draft.")
        return redirect("/admin-panel/combos")

    qs = ComboPackage.objects.prefetch_related("items__variant", "images")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    sort = request.GET.get("sort", "")
    qs = qs.order_by({
        "name":       "name",
        "price_asc":  "selling_price",
        "price_desc": "-selling_price",
        "orders":     "-orders_count",
        "newest":     "-created_at",
        "oldest":     "created_at",
    }.get(sort, "position"))

    all_qs = ComboPackage.objects.all()
    total_combos    = all_qs.count()
    active_combos   = all_qs.filter(status=ComboPackage.Status.ACTIVE).count()
    featured_combos = all_qs.filter(is_featured=True).count()
    total_orders    = all_qs.aggregate(s=Sum("orders_count"))["s"] or 0

    active_prefetched = ComboPackage.objects.filter(
        status=ComboPackage.Status.ACTIVE
    ).prefetch_related("items__variant")
    savings_pcts = [c.savings_pct for c in active_prefetched if c.savings_pct > 0]
    avg_savings = round(sum(savings_pcts) / len(savings_pcts), 1) if savings_pcts else 0

    combo_revenue = sum(
        c.selling_price * c.orders_count
        for c in all_qs
    )

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(request, "panel/combos.html", {
        "combos":         page_obj,
        "page_obj":       page_obj,
        "filtered_total": qs.count(),
        "q":              q,
        "status_filter":  status_filter,
        "sort":           sort,
        "total_combos":   total_combos,
        "active_combos":  active_combos,
        "featured_combos": featured_combos,
        "total_orders":   total_orders,
        "avg_savings":    avg_savings,
        "combo_revenue":  combo_revenue,
        "status_choices": ComboPackage.Status.choices,
    })


@admin_required
def combo_variant_search(request):
    from django.http import JsonResponse
    q = request.GET.get("q", "").strip()
    if len(q) >= 2:
        variants = (ProductVariant.objects
                    .filter(
                        Q(product__name__icontains=q) | Q(va_code__icontains=q),
                        product__status=Status.ACTIVE, status=Status.ACTIVE,
                    )
                    .select_related("product")[:10])
    else:
        # Return popular variants as suggestions when no query
        variants = (ProductVariant.objects
                    .filter(product__status=Status.ACTIVE, status=Status.ACTIVE)
                    .select_related("product")
                    .order_by("product__position", "position")[:8])
    results = [{
        "id":           v.pk,
        "name":         v.product.name,
        "variant":      v.variant,
        "sku":          v.va_code,
        "price":        v.selling_price,
        "stock":        v.stock,
        "stock_status": v.stock_status,
        "image":        v.product.image or "",
    } for v in variants]
    return JsonResponse({"results": results})


@admin_required
def combo_edit(request, pk=None):
    combo = get_object_or_404(ComboPackage, pk=pk) if pk else None
    items  = list(combo.items.select_related("variant__product").order_by("position")) if combo else []
    images = list(combo.images.all()) if combo else []

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Combo name is required.")
            return redirect(request.path)

        if not combo:
            combo = ComboPackage()
            combo.code = gen_code("CMB")

        combo.name              = name
        combo.slug              = slugify(name)
        combo.short_description = request.POST.get("short_description", "")
        combo.description       = request.POST.get("description", "")
        combo.badge_label       = request.POST.get("badge_label", "")
        combo.badge_style       = request.POST.get("badge_style", "")
        combo.tags              = request.POST.get("tags", "")
        combo.selling_price     = float(request.POST.get("selling_price", "0") or "0")
        mrp_raw                 = request.POST.get("mrp_price", "")
        combo.mrp_price         = float(mrp_raw) if mrp_raw else None
        combo.gst_rate          = float(request.POST.get("gst_rate", "5") or "5")
        combo.status            = request.POST.get("status", ComboPackage.Status.DRAFT)
        combo.is_featured       = request.POST.get("is_featured") == "1"
        combo.is_limited_time   = request.POST.get("is_limited_time") == "1"
        combo.is_cod_available  = request.POST.get("is_cod_available") == "1"
        combo.available_from    = request.POST.get("available_from") or None
        combo.available_until   = request.POST.get("available_until") or None
        combo.max_qty_per_order = int(request.POST.get("max_qty_per_order", "10") or "10")

        base_slug = combo.slug
        counter = 1
        while ComboPackage.objects.filter(slug=combo.slug).exclude(pk=combo.pk or 0).exists():
            combo.slug = f"{base_slug}-{counter}"
            counter += 1

        combo.save()

        variant_ids = request.POST.getlist("item_variant_id")
        quantities  = request.POST.getlist("item_qty")
        combo.items.all().delete()
        for i, (vid, qty) in enumerate(zip(variant_ids, quantities)):
            try:
                v = ProductVariant.objects.get(pk=int(vid))
                ComboItem.objects.create(combo=combo, variant=v,
                                         quantity=int(qty or 1), position=i)
            except (ProductVariant.DoesNotExist, ValueError):
                pass

        image_urls = request.POST.getlist("image_url")
        image_main = request.POST.get("image_main_idx", "0")
        combo.images.all().delete()
        for i, url in enumerate(image_urls):
            if url.strip():
                ComboImage.objects.create(
                    combo=combo, url=url.strip(),
                    is_main=(str(i) == image_main), position=i,
                )

        label = "published" if combo.status == ComboPackage.Status.ACTIVE else "saved as draft"
        messages.success(request, f'Combo "{combo.name}" {label}.')
        return redirect(f"/admin-panel/combos/{combo.pk}/edit")

    return render(request, "panel/combo_edit.html", {
        "combo":          combo,
        "combo_items":    items,
        "combo_images":   images,
        "badge_styles":   ComboPackage.BadgeStyle.choices,
        "gst_rates": [
            ("0",  "0% (Exempt)"),
            ("5",  "5% (Food Products)"),
            ("12", "12%"),
            ("18", "18%"),
            ("28", "28%"),
        ],
        "status_choices": ComboPackage.Status.choices,
    })


@admin_required
def combo_delete(request, pk):
    combo = get_object_or_404(ComboPackage, pk=pk)
    name = combo.name
    combo.delete()
    messages.success(request, f'Combo "{name}" deleted.')
    return redirect("/admin-panel/combos")


# --------------------------------------------------------------------------- #
# Reviews module
# --------------------------------------------------------------------------- #

AVATAR_STYLES = [
    "bg-brand-100 text-brand-700",
    "bg-blue-100 text-blue-700",
    "bg-purple-100 text-purple-700",
    "bg-orange-100 text-orange-700",
    "bg-teal-100 text-teal-700",
    "bg-rose-100 text-rose-700",
    "bg-indigo-100 text-indigo-700",
    "bg-amber-100 text-amber-700",
]


@admin_required
def reviews_list(request):
    from datetime import timedelta
    from django.http import JsonResponse

    # Bulk POST actions
    if request.method == "POST":
        action = request.POST.get("action", "")
        ids = request.POST.getlist("ids")
        if ids:
            if action == "delete":
                Review.objects.filter(pk__in=ids).delete()
                messages.success(request, f"Deleted {len(ids)} review(s).")
            elif action == "approve":
                Review.objects.filter(pk__in=ids).update(status=ReviewStatus.APPROVED)
                messages.success(request, f"Approved {len(ids)} review(s).")
            elif action == "reject":
                Review.objects.filter(pk__in=ids).update(status=ReviewStatus.REJECTED)
                messages.success(request, f"Rejected {len(ids)} review(s).")
            elif action == "unflag":
                Review.objects.filter(pk__in=ids).update(is_flagged=False)
                messages.success(request, f"Unflagged {len(ids)} review(s).")
        return redirect("/admin-panel/reviews")

    # Period
    try:
        period = int(request.GET.get("period", "30") or "30")
    except ValueError:
        period = 30

    now = timezone.now()
    if period > 0:
        since = now - timedelta(days=period)
        period_qs = Review.objects.filter(created_at__gte=since)
    else:
        period_qs = Review.objects.all()
        since = None

    approved_qs = period_qs.filter(status=ReviewStatus.APPROVED)
    total_count = approved_qs.count()
    avg_rating_val = approved_qs.aggregate(a=Avg("rating"))["a"] or 0
    avg_rating = round(avg_rating_val, 1)

    # Compare to previous period
    if period > 0 and since is not None:
        prev_since = since - timedelta(days=period)
        prev_avg = (
            Review.objects.filter(
                created_at__gte=prev_since, created_at__lt=since,
                status=ReviewStatus.APPROVED
            ).aggregate(a=Avg("rating"))["a"] or 0
        )
        avg_diff = round(avg_rating - prev_avg, 1)
    else:
        avg_diff = 0

    # Rating breakdown (5→1 descending for display)
    breakdown = {}
    for i in range(1, 6):
        breakdown[i] = approved_qs.filter(rating=i).count()
    breakdown_list = [
        {
            "star": i,
            "count": breakdown[i],
            "pct": round(breakdown[i] / total_count * 100) if total_count else 0,
        }
        for i in range(5, 0, -1)
    ]

    # Health metrics
    all_period = period_qs.count()
    replied_count = period_qs.exclude(reply="").count()
    response_rate = round(replied_count / all_period * 100) if all_period else 0
    pending_replies = period_qs.filter(status=ReviewStatus.APPROVED, reply="").count()
    flagged_count = period_qs.filter(is_flagged=True).count()

    # Avg response time (hours)
    replied_timing = list(
        period_qs.filter(replied_at__isnull=False).values("created_at", "replied_at")
    )
    if replied_timing:
        total_secs = sum(
            (r["replied_at"] - r["created_at"]).total_seconds() for r in replied_timing
        )
        avg_response_hrs = round(total_secs / len(replied_timing) / 3600, 1)
    else:
        avg_response_hrs = 0

    # Filters
    q = request.GET.get("q", "").strip()
    product_filter = request.GET.get("product", "")
    rating_filter = request.GET.get("rating", "")
    reply_filter = request.GET.get("replied", "")
    sort = request.GET.get("sort", "-created_at")

    qs = period_qs.select_related("user", "product")

    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(comment__icontains=q) |
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) |
            Q(product__name__icontains=q)
        )
    if product_filter:
        qs = qs.filter(product_id=product_filter)
    if rating_filter:
        try:
            qs = qs.filter(rating=int(rating_filter))
        except ValueError:
            pass
    if reply_filter == "replied":
        qs = qs.exclude(reply="")
    elif reply_filter == "unreplied":
        qs = qs.filter(reply="")
    elif reply_filter == "flagged":
        qs = qs.filter(is_flagged=True)

    sort_map = {
        "-created_at": "-created_at",
        "created_at": "created_at",
        "-rating": "-rating",
        "rating": "rating",
        "-helpful_count": "-helpful_count",
    }
    qs = qs.order_by(sort_map.get(sort, "-created_at"))

    products_with_reviews = (
        Product.objects.filter(reviews__isnull=False).distinct().order_by("name")
    )

    paginator = Paginator(qs, 7)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    for r in page_obj:
        r.avatar_style = AVATAR_STYLES[r.user_id % len(AVATAR_STYLES)]
        r.initials = (
            ((r.user.first_name or "")[:1] + (r.user.last_name or "")[:1]).upper()
            or (r.user.email or "?")[:1].upper()
        )

    return render(request, "panel/reviews.html", {
        "active_path": "/admin-panel/reviews",
        "reviews": page_obj,
        "page_obj": page_obj,
        "filtered_total": qs.count(),
        "period": period,
        "avg_rating": avg_rating,
        "avg_diff": avg_diff,
        "total_count": total_count,
        "breakdown": breakdown,
        "breakdown_list": breakdown_list,
        "response_rate": response_rate,
        "pending_replies": pending_replies,
        "flagged_count": flagged_count,
        "avg_response_hrs": avg_response_hrs,
        "q": q,
        "product_filter": product_filter,
        "rating_filter": rating_filter,
        "reply_filter": reply_filter,
        "sort": sort,
        "products_with_reviews": products_with_reviews,
    })


@admin_required
def review_reply(request, pk):
    from django.http import JsonResponse

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    review = get_object_or_404(Review, pk=pk)
    reply_text = request.POST.get("reply", "").strip()
    if not reply_text:
        return JsonResponse({"error": "Reply text cannot be empty."}, status=400)

    review.reply = reply_text
    review.replied_at = timezone.now()
    review.save(update_fields=["reply", "replied_at"])

    return JsonResponse({"ok": True, "reply": reply_text})


@admin_required
def review_flag(request, pk):
    from django.http import JsonResponse

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    review = get_object_or_404(Review, pk=pk)
    review.is_flagged = not review.is_flagged
    review.save(update_fields=["is_flagged"])

    return JsonResponse({"ok": True, "flagged": review.is_flagged})


@admin_required
def review_delete(request, pk):
    if request.method != "POST":
        return redirect("/admin-panel/reviews")
    review = get_object_or_404(Review, pk=pk)
    review.delete()
    messages.success(request, "Review deleted.")
    return redirect(request.POST.get("next", "/admin-panel/reviews"))


@admin_required
def review_export(request):
    period = int(request.GET.get("period", "30") or "0")
    now = timezone.now()
    qs = Review.objects.select_related("user", "product").order_by("-created_at")
    if period > 0:
        from datetime import timedelta
        qs = qs.filter(created_at__gte=now - timedelta(days=period))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="reviews.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "ID", "Customer", "Email", "Product", "Rating", "Title",
        "Comment", "Reply", "Status", "Verified", "Flagged",
        "Helpful Count", "Date",
    ])
    for r in qs:
        writer.writerow([
            r.pk,
            f"{r.user.first_name} {r.user.last_name}".strip() or r.user.email,
            r.user.email,
            r.product.name,
            r.rating,
            r.title,
            r.comment,
            r.reply,
            r.status,
            r.is_verified,
            r.is_flagged,
            r.helpful_count,
            r.created_at.strftime("%Y-%m-%d %H:%M"),
        ])
    return response


# --------------------------------------------------------------------------- #
# Banners
# --------------------------------------------------------------------------- #

@admin_required
def banners_list(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        ids = request.POST.getlist("ids")
        if ids:
            if action == "delete":
                Banner.objects.filter(pk__in=ids).delete()
                messages.success(request, f"Deleted {len(ids)} banner(s).")
            elif action == "activate":
                Banner.objects.filter(pk__in=ids).update(status=Status.ACTIVE)
            elif action == "deactivate":
                Banner.objects.filter(pk__in=ids).update(status=Status.INACTIVE)
        return redirect("/admin-panel/banners")

    q = request.GET.get("q", "").strip()
    type_filter = request.GET.get("type", "")
    status_filter = request.GET.get("status", "")

    qs = Banner.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    if type_filter:
        qs = qs.filter(type=type_filter)
    if status_filter:
        qs = qs.filter(status=status_filter)

    total   = Banner.objects.count()
    active  = Banner.objects.filter(status=Status.ACTIVE).count()
    by_type = {t: Banner.objects.filter(type=t).count() for t, _ in BannerType.choices}

    return render(request, "panel/banners.html", {
        "active_path": "/admin-panel/banners",
        "banners": qs,
        "total": total,
        "active_count": active,
        "inactive_count": total - active,
        "by_type": by_type,
        "type_choices": BannerType.choices,
        "q": q,
        "type_filter": type_filter,
        "status_filter": status_filter,
    })


@admin_required
def banner_edit(request, pk=None):
    banner = get_object_or_404(Banner, pk=pk) if pk else None

    if request.method == "POST":
        name        = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        image       = request.POST.get("image", "").strip()
        video_url   = request.POST.get("video_url", "").strip()
        btype       = request.POST.get("type", BannerType.HOME_BANNER)
        try:
            position = int(request.POST.get("position", 1) or 1)
        except ValueError:
            position = 1
        status_val  = request.POST.get("status", Status.ACTIVE)

        if not name:
            messages.error(request, "Banner name is required.")
            return redirect(request.path)

        if banner:
            banner.name        = name
            banner.description = description
            banner.image       = image
            banner.video_url   = video_url or None
            banner.type        = btype
            banner.position    = position
            banner.status      = status_val
            banner.save()
            messages.success(request, f'Banner "{name}" updated.')
        else:
            Banner.objects.create(
                name=name, description=description, image=image,
                video_url=video_url or None, type=btype,
                position=position, status=status_val,
            )
            messages.success(request, f'Banner "{name}" created.')
        return redirect("/admin-panel/banners")

    return render(request, "panel/banner_form.html", {
        "active_path": "/admin-panel/banners",
        "banner": banner,
        "type_choices": BannerType.choices,
        "status_choices": Status.choices,
    })


@admin_required
def banner_delete(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    name = banner.name
    banner.delete()
    messages.success(request, f'Banner "{name}" deleted.')
    return redirect("/admin-panel/banners")


@admin_required
def banner_toggle(request, pk):
    from django.http import JsonResponse
    banner = get_object_or_404(Banner, pk=pk)
    banner.status = Status.INACTIVE if banner.status == Status.ACTIVE else Status.ACTIVE
    banner.save(update_fields=["status"])
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "status": banner.status})
    return redirect("/admin-panel/banners")


# --------------------------------------------------------------------------- #
# Coupons
# --------------------------------------------------------------------------- #

@admin_required
def coupons_list(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        ids = request.POST.getlist("ids")
        if ids:
            if action == "delete":
                Coupon.objects.filter(pk__in=ids).delete()
                messages.success(request, f"Deleted {len(ids)} coupon(s).")
            elif action == "activate":
                Coupon.objects.filter(pk__in=ids).update(is_active=True)
            elif action == "deactivate":
                Coupon.objects.filter(pk__in=ids).update(is_active=False)
        return redirect("/admin-panel/coupons")

    q            = request.GET.get("q", "").strip()
    type_filter  = request.GET.get("type", "")
    status_filter= request.GET.get("status", "")
    sort         = request.GET.get("sort", "-created_at")

    qs = Coupon.objects.all()
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(description__icontains=q))
    if type_filter:
        qs = qs.filter(coupon_type=type_filter)
    if status_filter == "active":
        qs = qs.filter(is_active=True)
    elif status_filter == "inactive":
        qs = qs.filter(is_active=False)

    sort_map = {
        "-created_at": "-created_at", "created_at": "created_at",
        "-used_count": "-used_count", "code": "code",
    }
    qs = qs.order_by(sort_map.get(sort, "-created_at"))

    now = timezone.now()
    total     = Coupon.objects.count()
    active    = Coupon.objects.filter(is_active=True).count()
    expired   = sum(1 for c in Coupon.objects.all() if c.is_expired)
    total_uses = Coupon.objects.aggregate(s=Sum("used_count"))["s"] or 0

    paginator = Paginator(qs, 15)
    page_obj  = paginator.get_page(request.GET.get("page", 1))

    return render(request, "panel/coupons.html", {
        "active_path": "/admin-panel/coupons",
        "coupons": page_obj,
        "page_obj": page_obj,
        "filtered_total": qs.count(),
        "total": total,
        "active_count": active,
        "expired_count": expired,
        "total_uses": total_uses,
        "type_choices": CouponType.choices,
        "q": q,
        "type_filter": type_filter,
        "status_filter": status_filter,
        "sort": sort,
        "now": now,
    })


@admin_required
def coupon_edit(request, pk=None):
    coupon = get_object_or_404(Coupon, pk=pk) if pk else None

    if request.method == "POST":
        code            = request.POST.get("code", "").strip().upper()
        description     = request.POST.get("description", "").strip()
        coupon_type     = request.POST.get("coupon_type", CouponType.PERCENT)
        try:
            discount_value  = float(request.POST.get("discount_value", 0) or 0)
            min_order_value = float(request.POST.get("min_order_value", 0) or 0)
            max_uses        = int(request.POST.get("max_uses", 0) or 0)
        except ValueError:
            discount_value = min_order_value = 0
            max_uses = 0

        max_disc_raw = request.POST.get("max_discount", "").strip()
        max_discount = float(max_disc_raw) if max_disc_raw else None

        valid_from_raw  = request.POST.get("valid_from", "").strip()
        valid_until_raw = request.POST.get("valid_until", "").strip()
        from django.utils.dateparse import parse_datetime
        valid_from  = parse_datetime(valid_from_raw) if valid_from_raw else None
        valid_until = parse_datetime(valid_until_raw) if valid_until_raw else None

        is_active = request.POST.get("is_active") == "1"

        if not code:
            messages.error(request, "Coupon code is required.")
            return redirect(request.path)

        if coupon:
            # Check uniqueness (excluding self)
            if Coupon.objects.exclude(pk=coupon.pk).filter(code=code).exists():
                messages.error(request, f'Code "{code}" is already in use.')
                return redirect(request.path)
            coupon.code = code; coupon.description = description
            coupon.coupon_type = coupon_type; coupon.discount_value = discount_value
            coupon.min_order_value = min_order_value; coupon.max_discount = max_discount
            coupon.max_uses = max_uses; coupon.valid_from = valid_from
            coupon.valid_until = valid_until; coupon.is_active = is_active
            coupon.save()
            messages.success(request, f'Coupon "{code}" updated.')
        else:
            if Coupon.objects.filter(code=code).exists():
                messages.error(request, f'Code "{code}" already exists.')
                return redirect(request.path)
            Coupon.objects.create(
                code=code, description=description, coupon_type=coupon_type,
                discount_value=discount_value, min_order_value=min_order_value,
                max_discount=max_discount, max_uses=max_uses,
                valid_from=valid_from, valid_until=valid_until, is_active=is_active,
            )
            messages.success(request, f'Coupon "{code}" created.')
        return redirect("/admin-panel/coupons")

    return render(request, "panel/coupon_form.html", {
        "active_path": "/admin-panel/coupons",
        "coupon": coupon,
        "type_choices": CouponType.choices,
    })


@admin_required
def coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    code = coupon.code
    coupon.delete()
    messages.success(request, f'Coupon "{code}" deleted.')
    return redirect("/admin-panel/coupons")


@admin_required
def coupon_toggle(request, pk):
    from django.http import JsonResponse
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.is_active = not coupon.is_active
    coupon.save(update_fields=["is_active"])
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "active": coupon.is_active})
    return redirect("/admin-panel/coupons")
