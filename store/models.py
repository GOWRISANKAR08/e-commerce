"""
Store models — faithful port of the Prisma schema (catalog, cart, orders,
reviews, marketing & content). Table names and field mappings mirror Prisma's
`@@map` / `@map` directives so the schema matches the original MySQL layout.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Status


# --------------------------------------------------------------------------- #
# Enums (Prisma enums -> TextChoices)
# --------------------------------------------------------------------------- #
class StockStatus(models.TextChoices):
    IN_STOCK = "IN_STOCK", "In Stock"
    LOW_STOCK = "LOW_STOCK", "Low Stock"
    OUT_OF_STOCK = "OUT_OF_STOCK", "Out of Stock"


class OrderStatus(models.TextChoices):
    PROCESSING = "PROCESSING", "Processing"
    ORDER_CONFIRMED = "ORDER_CONFIRMED", "Order Confirmed"
    PACKED = "PACKED", "Packed"
    DISPATCHED = "DISPATCHED", "Dispatched"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"
    REFUNDED = "REFUNDED", "Refunded"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"
    CANCELLED = "CANCELLED", "Cancelled"


class PaymentMode(models.TextChoices):
    COD = "COD", "Cash on Delivery"
    RAZORPAY = "RAZORPAY", "Razorpay"


class OrderChannel(models.TextChoices):
    WEBSITE = "WEBSITE", "Website"
    INSTAGRAM = "INSTAGRAM", "Instagram"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    REFERRAL = "REFERRAL", "Referral"


class ReviewStatus(models.TextChoices):
    PENDING  = "PENDING",  "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    FLAGGED  = "FLAGGED",  "Flagged"


class BannerType(models.TextChoices):
    HOME_BANNER = "HOME_BANNER", "Home Banner"
    BRAND = "BRAND", "Brand Video"
    OFFER_BANNER = "OFFER_BANNER", "Offer Banner"


class PolicyType(models.TextChoices):
    ABOUT_US = "ABOUT_US", "About Us"
    TERMS    = "TERMS",    "Terms & Conditions"
    PRIVACY  = "PRIVACY",  "Privacy Policy"
    SHIPPING = "SHIPPING", "Shipping Policy"
    RETURNS  = "RETURNS",  "Return & Refund Policy"
    CONTACT  = "CONTACT",  "Contact Us"


class EnquiryStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    CLOSED = "CLOSED", "Closed"


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #
class ParentCategory(models.Model):
    name = models.CharField(max_length=150)
    image = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(default=1, db_column="is_position")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "parent_categories"
        verbose_name_plural = "Parent categories"

    def __str__(self):
        return self.name


class Category(models.Model):
    parent = models.ForeignKey(
        ParentCategory, related_name="categories", null=True, blank=True,
        on_delete=models.SET_NULL, db_column="parent_category_id",
    )
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.CharField(max_length=255, blank=True, default="")
    image = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(default=1, db_column="is_position")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    coming_soon = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"
        verbose_name_plural = "Categories"
        ordering = ["position"]

    def __str__(self):
        return self.name


class Product(models.Model):
    code = models.CharField(max_length=64, unique=True)
    category = models.ForeignKey(Category, related_name="products", on_delete=models.CASCADE,
                                 db_column="category_id")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(null=True, blank=True)
    image = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    top_seller = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    badge = models.CharField(max_length=40, null=True, blank=True)  # Bestseller/Organic/New/Wellness
    position = models.IntegerField(default=1, db_column="is_position")
    youtube_link = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        ordering = ["position"]
        indexes = [models.Index(fields=["category"])]

    def __str__(self):
        return self.name

    @property
    def active_variants(self):
        return self.variants.filter(status=Status.ACTIVE).order_by("position")

    @property
    def default_variant(self):
        return self.active_variants.first()

    @property
    def avg_rating(self):
        rs = [r.rating for r in self.reviews.filter(status=ReviewStatus.APPROVED)]
        return round(sum(rs) / len(rs), 1) if rs else 0

    @property
    def review_count(self):
        return self.reviews.filter(status=ReviewStatus.APPROVED).count()


class ProductVariant(models.Model):
    va_code = models.CharField(max_length=120, unique=True)
    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE,
                                db_column="product_id")
    variant = models.CharField(max_length=60)        # "50g", "100g", "250g"
    short_name = models.CharField(max_length=60, null=True, blank=True)
    selling_price = models.FloatField()
    mrp_price = models.FloatField()
    stock = models.IntegerField(default=0)
    reserved_stock = models.IntegerField(default=0)  # committed to confirmed orders
    weight_in_gm = models.FloatField(default=0)
    stock_status = models.CharField(max_length=14, choices=StockStatus.choices,
                                    default=StockStatus.IN_STOCK)
    position = models.IntegerField(default=1, db_column="is_position")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "product_varients"
        ordering = ["position"]

    def __str__(self):
        return f"{self.product.name} — {self.variant}"

    @property
    def discount_pct(self):
        if not self.mrp_price or self.mrp_price <= self.selling_price:
            return 0
        return round((self.mrp_price - self.selling_price) / self.mrp_price * 100)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE,
                                db_column="product_id")
    image = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "product_images"

    def __str__(self):
        return self.image


# --------------------------------------------------------------------------- #
# Combo Packs
# --------------------------------------------------------------------------- #
class ComboPackage(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DRAFT  = "DRAFT",  "Draft"

    class BadgeStyle(models.TextChoices):
        SPICE_RED   = "spice-red",   "Spice Red (Secondary)"
        BRAND_GREEN = "brand-green", "Brand Green (Primary)"
        GOLD        = "gold",        "Gold"
        DARK        = "dark",        "Dark"

    code              = models.CharField(max_length=20, unique=True)
    name              = models.CharField(max_length=200)
    slug              = models.SlugField(max_length=220, unique=True)
    short_description = models.CharField(max_length=300, blank=True, default="")
    description       = models.TextField(blank=True, default="")
    badge_label       = models.CharField(max_length=50, blank=True, default="")
    badge_style       = models.CharField(max_length=20, choices=BadgeStyle.choices, blank=True, default="")
    tags              = models.CharField(max_length=500, blank=True, default="")
    selling_price     = models.FloatField(default=0)
    mrp_price         = models.FloatField(null=True, blank=True)
    gst_rate          = models.FloatField(default=5)
    is_featured       = models.BooleanField(default=False)
    is_limited_time   = models.BooleanField(default=False)
    is_cod_available  = models.BooleanField(default=True)
    status            = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    available_from    = models.DateField(null=True, blank=True)
    available_until   = models.DateField(null=True, blank=True)
    max_qty_per_order = models.PositiveIntegerField(default=10)
    orders_count      = models.PositiveIntegerField(default=0)
    position          = models.IntegerField(default=1)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "-created_at"]

    def __str__(self):
        return self.name

    @property
    def original_total(self):
        return sum(
            item.variant.selling_price * item.quantity
            for item in self.items.select_related("variant").all()
        )

    @property
    def savings(self):
        return max(0.0, self.original_total - self.selling_price)

    @property
    def savings_pct(self):
        orig = self.original_total
        if orig > 0 and self.selling_price < orig:
            return round((1 - self.selling_price / orig) * 100)
        return 0

    @property
    def main_image(self):
        img = self.images.filter(is_main=True).first() or self.images.first()
        return img.url if img else ""


class ComboItem(models.Model):
    combo    = models.ForeignKey(ComboPackage, on_delete=models.CASCADE, related_name="items")
    variant  = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="combo_items")
    quantity = models.PositiveIntegerField(default=1)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def line_total(self):
        return self.variant.selling_price * self.quantity


class ComboImage(models.Model):
    combo    = models.ForeignKey(ComboPackage, on_delete=models.CASCADE, related_name="images")
    url      = models.CharField(max_length=500)
    is_main  = models.BooleanField(default=False)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


# --------------------------------------------------------------------------- #
# Cart & favourites
# --------------------------------------------------------------------------- #
class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="cart",
                                on_delete=models.CASCADE, db_column="user_id")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_cart"

    @property
    def subtotal(self):
        return sum(i.price * i.qty for i in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE,
                             db_column="cart_id")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, db_column="varient_id")
    qty = models.IntegerField(default=1)
    price = models.FloatField(default=0)

    combo = models.ForeignKey(
        'ComboPackage', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cart_items',
    )

    class Meta:
        db_table = "product_cart_items"
        unique_together = ("cart", "variant")

    @property
    def line_total(self):
        return self.price * self.qty


class Favourite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="favourites",
                             on_delete=models.CASCADE, db_column="user_id")
    product = models.ForeignKey(Product, related_name="favourites", on_delete=models.CASCADE,
                                db_column="product_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favourites"
        unique_together = ("user", "product")


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
class Order(models.Model):
    order_id = models.CharField(max_length=64, unique=True)
    invoice_no = models.CharField(max_length=80)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="orders",
                             on_delete=models.CASCADE, db_column="user_id")
    sub_total = models.FloatField()
    discount = models.FloatField(default=0)
    shipping_amount = models.FloatField(default=0)
    grand_total = models.FloatField()
    status = models.CharField(max_length=20, choices=OrderStatus.choices,
                              default=OrderStatus.PROCESSING)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices,
                                      default=PaymentStatus.PENDING)
    payment_mode = models.CharField(max_length=12, choices=PaymentMode.choices,
                                     default=PaymentMode.COD)
    channel = models.CharField(max_length=12, choices=OrderChannel.choices,
                               default=OrderChannel.WEBSITE)
    razorpay_order_id   = models.CharField(max_length=120, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=120, null=True, blank=True)
    coupon              = models.ForeignKey("Coupon", null=True, blank=True,
                                            on_delete=models.SET_NULL,
                                            related_name="coupon_orders")
    coupon_discount     = models.FloatField(default=0)
    shipping_address    = models.TextField()
    no_of_product = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_id


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE,
                              to_field="order_id", db_column="order_id")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, db_column="product_id")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, db_column="varient_id")
    combo = models.ForeignKey(
        'ComboPackage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='order_items',
    )
    name = models.CharField(max_length=200)
    variant_label = models.CharField(max_length=60, db_column="variant")
    price = models.FloatField()
    qty = models.IntegerField()
    net_total = models.FloatField()

    class Meta:
        db_table = "order_items"


# --------------------------------------------------------------------------- #
# Reviews
# --------------------------------------------------------------------------- #
class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="reviews",
                             on_delete=models.CASCADE, db_column="user_id")
    product = models.ForeignKey(Product, related_name="reviews", on_delete=models.CASCADE,
                                db_column="product_id")
    rating = models.IntegerField(default=5)
    title = models.CharField(max_length=200, blank=True, default="")
    comment = models.TextField()
    status = models.CharField(max_length=10, choices=ReviewStatus.choices,
                              default=ReviewStatus.PENDING)
    reply = models.TextField(blank=True, default="")
    replied_at = models.DateTimeField(null=True, blank=True)
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=500, blank=True, default="")
    helpful_count = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=True)
    is_anonymous = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews"
        unique_together = ("user", "product")
        ordering = ["-created_at"]

    @property
    def can_edit(self):
        from django.utils import timezone
        return (timezone.now() - self.created_at).total_seconds() < 86400


class ReviewImage(models.Model):
    review = models.ForeignKey(Review, related_name="images", on_delete=models.CASCADE)
    image_url = models.CharField(max_length=500)
    public_id = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_images"


# --------------------------------------------------------------------------- #
# Marketing & content
# --------------------------------------------------------------------------- #
class Banner(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    image = models.CharField(max_length=255)
    video_url = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=14, choices=BannerType.choices,
                            default=BannerType.HOME_BANNER)
    position = models.IntegerField(default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "banners"
        ordering = ["position"]

    def __str__(self):
        return self.name


class Blog(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    image = models.CharField(max_length=255, null=True, blank=True)
    tag = models.CharField(max_length=60, null=True, blank=True)
    description = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "blogs"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Testimonial(models.Model):
    # Core fields (original)
    name     = models.CharField(max_length=150)
    city     = models.CharField(max_length=120, null=True, blank=True)
    image    = models.CharField(max_length=500, null=True, blank=True)
    rating   = models.IntegerField(default=5)
    comment  = models.TextField()
    position = models.IntegerField(default=0)
    status   = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    # Customer-submission fields
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="testimonials")
    email           = models.EmailField(blank=True)
    order           = models.ForeignKey("Order", null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="+")
    title           = models.CharField(max_length=200, blank=True)
    consent         = models.BooleanField(default=True)
    is_featured     = models.BooleanField(default=False)
    admin_note      = models.TextField(blank=True)
    approval_status = models.CharField(max_length=10, choices=ReviewStatus.choices,
                                       default=ReviewStatus.APPROVED)

    class Meta:
        db_table = "testimonials"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Faq(models.Model):
    category  = models.ForeignKey("FaqCategory", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="items")
    question  = models.TextField()
    answer    = models.TextField()
    position  = models.IntegerField(default=0)
    status    = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "faq"
        verbose_name = "FAQ"
        ordering = ["position"]

    def __str__(self):
        return self.question[:60]


class HomeOffer(models.Model):
    offer_name = models.CharField(max_length=200)
    to_date = models.DateTimeField()
    product_ids = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "home_offers"
        ordering = ["position"]

    def __str__(self):
        return self.offer_name


class CouponType(models.TextChoices):
    PERCENT      = "PERCENT",      "Percentage Off"
    FLAT         = "FLAT",         "Flat Amount Off"
    FREE_SHIPPING = "FREE_SHIPPING", "Free Shipping"


class Coupon(models.Model):
    code            = models.CharField(max_length=30, unique=True)
    name            = models.CharField(max_length=200, blank=True, default="")
    description     = models.CharField(max_length=500, blank=True, default="")
    coupon_type     = models.CharField(max_length=15, choices=CouponType.choices,
                                       default=CouponType.PERCENT)
    discount_value  = models.FloatField(default=0)
    min_order_value = models.FloatField(default=0)
    max_discount    = models.FloatField(null=True, blank=True)
    max_uses        = models.PositiveIntegerField(default=0)
    per_user_limit  = models.PositiveIntegerField(default=0)
    used_count      = models.PositiveIntegerField(default=0)
    valid_from      = models.DateTimeField(null=True, blank=True)
    valid_until     = models.DateTimeField(null=True, blank=True)
    channels        = models.CharField(max_length=100, blank=True, default="WEBSITE")
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "coupons"
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    @property
    def status_tag(self):
        """Returns Active / Scheduled / Expired / Inactive."""
        now = timezone.now()
        if not self.is_active:
            return "Inactive"
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return "Expired"
        if self.valid_until and now > self.valid_until:
            return "Expired"
        if self.valid_from and now < self.valid_from:
            return "Scheduled"
        return "Active"

    @property
    def is_expired(self):
        return self.status_tag == "Expired"

    @property
    def status_label(self):
        return self.status_tag

    @property
    def usage_pct(self):
        if self.max_uses > 0:
            return round(self.used_count / self.max_uses * 100)
        return 0

    @property
    def channel_list(self):
        return [c.strip() for c in self.channels.split(",") if c.strip()]

    def compute_discount(self, cart_total):
        """Return the discount amount for a given cart total."""
        if self.coupon_type == CouponType.PERCENT:
            d = cart_total * self.discount_value / 100
            if self.max_discount:
                d = min(d, self.max_discount)
            return round(d, 2)
        if self.coupon_type == CouponType.FLAT:
            return round(min(self.discount_value, cart_total), 2)
        if self.coupon_type == CouponType.FREE_SHIPPING:
            return 0  # handled separately in checkout
        return 0


class Policy(models.Model):
    type    = models.CharField(max_length=12, choices=PolicyType.choices, unique=True)
    title   = models.CharField(max_length=200)
    content = models.TextField()
    # SEO
    meta_title       = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords    = models.CharField(max_length=500, blank=True)
    og_image         = models.CharField(max_length=500, blank=True)
    # Lifecycle
    is_published = models.BooleanField(default=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_policies"
        verbose_name_plural = "Policies"

    def __str__(self):
        return self.title


class Enquiry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="enquiries",
                             db_column="user_id")
    name    = models.CharField(max_length=150)
    email   = models.EmailField()
    mobile  = models.CharField(max_length=20, null=True, blank=True)
    subject = models.CharField(max_length=200, null=True, blank=True)
    message = models.TextField()
    status  = models.CharField(max_length=12, choices=EnquiryStatus.choices,
                               default=EnquiryStatus.OPEN)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "enquiries"
        verbose_name_plural = "Enquiries"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.subject or 'Enquiry'}"


class EnquiryReply(models.Model):
    enquiry    = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="replies")
    message    = models.TextField()
    sent_by    = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="enquiry_replies")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "enquiry_replies"
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply to {self.enquiry_id} @ {self.created_at:%Y-%m-%d}"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications",
                             on_delete=models.CASCADE, db_column="user_id")
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# --------------------------------------------------------------------------- #
# Inventory automation
# --------------------------------------------------------------------------- #
class StockThreshold(models.Model):
    """
    Configurable thresholds that drive automatic stock status computation.
    A row with product=None is the global default. Per-product rows override it.
    """
    product = models.OneToOneField(
        Product, null=True, blank=True, on_delete=models.CASCADE,
        related_name="threshold",
    )
    in_stock_min = models.PositiveIntegerField(
        default=51,
        help_text="Stock >= this value → In Stock",
    )
    low_stock_min = models.PositiveIntegerField(
        default=1,
        help_text="Stock >= this value (and < in_stock_min) → Low Stock; below → Out of Stock",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Stock Threshold"

    def __str__(self):
        label = self.product.name if self.product_id else "Global"
        return f"Threshold ({label}): ≥{self.in_stock_min} In Stock, ≥{self.low_stock_min} Low"

    @classmethod
    def get_for_product(cls, product):
        """Return the threshold applicable to *product*, falling back to global."""
        try:
            return cls.objects.get(product=product)
        except cls.DoesNotExist:
            pass
        try:
            return cls.objects.get(product__isnull=True)
        except cls.DoesNotExist:
            return cls(in_stock_min=51, low_stock_min=1)

    def compute_status(self, stock: int) -> str:
        stock = max(int(stock or 0), 0)
        if stock >= self.in_stock_min:
            return StockStatus.IN_STOCK
        if stock >= self.low_stock_min:
            return StockStatus.LOW_STOCK
        return StockStatus.OUT_OF_STOCK


class OrderRefund(models.Model):
    """Records full or partial refunds issued for an order."""
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    TYPE_CHOICES = [(FULL, "Full Refund"), (PARTIAL, "Partial Refund")]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="refunds")
    refund_type = models.CharField(max_length=8, choices=TYPE_CHOICES, default=FULL)
    amount = models.FloatField()
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund {self.refund_type} ₹{self.amount} for {self.order_id}"


class OrderNote(models.Model):
    """Internal or customer-visible notes on an order."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="notes")
    text = models.TextField()
    is_internal = models.BooleanField(default=True)
    created_by_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_notes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note on {self.order_id} at {self.created_at:%Y-%m-%d}"


class OrderEvent(models.Model):
    """Immutable timeline log for an order (status changes, notes, payments, etc.)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    actor_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_events"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.title} — {self.order_id}"


class StockStatusHistory(models.Model):
    """Audit log of every stock status change on a product variant."""
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="status_history",
    )
    old_status = models.CharField(max_length=14, blank=True)
    new_status = models.CharField(max_length=14)
    old_stock = models.IntegerField(default=0)
    new_stock = models.IntegerField(default=0)
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Stock Status History"
        verbose_name_plural = "Stock Status Histories"

    def __str__(self):
        return f"{self.variant} · {self.old_status}→{self.new_status}"


# --------------------------------------------------------------------------- #
# Integration configuration (Razorpay, Firebase Storage, etc.)
# --------------------------------------------------------------------------- #
class IntegrationConfig(models.Model):
    class Integration(models.TextChoices):
        RAZORPAY   = "RAZORPAY",   "Razorpay"
        CLOUDINARY = "CLOUDINARY", "Cloudinary"
        EMAIL      = "EMAIL",      "Email (SMTP)"

    integration = models.CharField(max_length=20, choices=Integration.choices)
    key         = models.CharField(max_length=100)
    value       = models.TextField(blank=True, default="")
    is_secret   = models.BooleanField(default=False)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("integration", "key")
        ordering = ["integration", "key"]

    def __str__(self):
        return f"{self.integration}.{self.key}"

    @classmethod
    def get(cls, integration, key, default=""):
        try:
            return cls.objects.get(integration=integration, key=key).value or default
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_value(cls, integration, key, value, is_secret=False):
        obj, _ = cls.objects.get_or_create(
            integration=integration, key=key,
            defaults={"is_secret": is_secret},
        )
        obj.value = value
        obj.is_secret = is_secret
        obj.save(update_fields=["value", "is_secret", "updated_at"])


# --------------------------------------------------------------------------- #
# Site-wide settings (singleton — only one row, pk=1)
# --------------------------------------------------------------------------- #
class SiteSettings(models.Model):
    """Singleton: call SiteSettings.get() — never instantiate directly."""

    # Store Identity
    store_name     = models.CharField(max_length=100, default="Spicearog")
    store_tagline  = models.CharField(max_length=200, blank=True, default="Pure · Natural · Authentic")
    business_email = models.EmailField(blank=True, default="")
    support_phone  = models.CharField(max_length=20, blank=True, default="")
    store_address  = models.TextField(blank=True, default="")
    logo_url       = models.CharField(max_length=500, blank=True, default="")

    # Regional Settings
    currency        = models.CharField(max_length=50, default="INR — Indian Rupee (₹)")
    timezone        = models.CharField(max_length=60, default="IST — Asia/Kolkata (UTC+5:30)")
    language        = models.CharField(max_length=40, default="English (India)")
    date_format     = models.CharField(max_length=30, default="DD MMM YYYY")
    weight_unit     = models.CharField(max_length=20, default="Grams (g)")
    order_id_prefix = models.CharField(max_length=10, default="ORD-")

    # Shipping & Delivery
    free_shipping_above     = models.IntegerField(default=499)
    default_shipping_charge = models.IntegerField(default=49)
    processing_time         = models.CharField(max_length=20, default="1-2")
    estimated_delivery      = models.CharField(max_length=20, default="3-7")
    cod_enabled             = models.BooleanField(default=True)
    show_delivery_estimate  = models.BooleanField(default=True)
    international_shipping  = models.BooleanField(default=False)

    # Tax Configuration
    gstin                   = models.CharField(max_length=20, blank=True, default="")
    default_gst_rate        = models.CharField(max_length=10, default="5")
    prices_inclusive_of_gst = models.BooleanField(default=True)
    show_gst_in_invoice     = models.BooleanField(default=True)

    # Notification Preferences — Orders
    notif_new_order       = models.BooleanField(default=True)
    notif_order_cancelled = models.BooleanField(default=True)
    notif_refund_request  = models.BooleanField(default=True)
    notif_order_delivered = models.BooleanField(default=False)
    # Notification Preferences — Inventory
    notif_low_stock    = models.BooleanField(default=True)
    notif_out_of_stock = models.BooleanField(default=True)
    notif_restock      = models.BooleanField(default=False)
    notif_new_review   = models.BooleanField(default=True)
    # Notification Preferences — Marketing
    notif_customer_registered = models.BooleanField(default=True)
    notif_payment_success     = models.BooleanField(default=True)
    notif_payment_failed      = models.BooleanField(default=True)
    notif_promotional         = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "site_settings"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# --------------------------------------------------------------------------- #
# CMS — FAQ categories
# --------------------------------------------------------------------------- #
class FaqCategory(models.Model):
    name      = models.CharField(max_length=100)
    position  = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "faq_categories"
        ordering = ["position"]

    def __str__(self):
        return self.name


# --------------------------------------------------------------------------- #
# CMS — Team members (About Us)
# --------------------------------------------------------------------------- #
class TeamMember(models.Model):
    name      = models.CharField(max_length=100)
    role      = models.CharField(max_length=100)
    bio       = models.TextField(blank=True)
    photo_url = models.CharField(max_length=500, blank=True)
    position  = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "team_members"
        ordering = ["position"]

    def __str__(self):
        return f"{self.name} — {self.role}"


# --------------------------------------------------------------------------- #
# CMS — Revision history for Policy pages
# --------------------------------------------------------------------------- #
class CMSRevision(models.Model):
    page_type  = models.CharField(max_length=20)
    title      = models.CharField(max_length=200)
    content    = models.TextField()
    saved_by   = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="cms_revisions")
    note       = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cms_revisions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.page_type} — {self.created_at:%Y-%m-%d %H:%M}"


# --------------------------------------------------------------------------- #
# Razorpay payment — pending orders and audit log
# --------------------------------------------------------------------------- #
class PendingOrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID    = "PAID",    "Paid"
    FAILED  = "FAILED",  "Failed"
    EXPIRED = "EXPIRED", "Expired"


class PaymentAttemptStatus(models.TextChoices):
    INITIATED = "INITIATED",  "Initiated"
    SUCCESS   = "SUCCESS",    "Success"
    FAILED    = "FAILED",     "Failed"
    CANCELLED = "CANCELLED",  "Cancelled"


class RazorpayPendingOrder(models.Model):
    """
    Created when Razorpay checkout is initiated. Holds cart/address snapshot
    so the real Order can be created only after payment is confirmed.
    """
    order_code        = models.CharField(max_length=64, unique=True)
    razorpay_order_id = models.CharField(max_length=120, unique=True)
    user              = models.ForeignKey(settings.AUTH_USER_MODEL,
                                          on_delete=models.CASCADE,
                                          related_name="pending_rzp_orders")
    status            = models.CharField(max_length=12,
                                         choices=PendingOrderStatus.choices,
                                         default=PendingOrderStatus.PENDING)
    sub_total         = models.FloatField()
    coupon_discount   = models.FloatField(default=0)
    shipping_amount   = models.FloatField(default=0)
    grand_total       = models.FloatField()
    coupon            = models.ForeignKey("Coupon", null=True, blank=True,
                                          on_delete=models.SET_NULL)
    shipping_address  = models.TextField()
    cart_snapshot     = models.TextField()
    created_at        = models.DateTimeField(auto_now_add=True)
    expires_at        = models.DateTimeField()

    class Meta:
        db_table = "razorpay_pending_orders"

    def __str__(self):
        return f"{self.order_code} ({self.status})"

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at


class PaymentAttempt(models.Model):
    """Audit log for every Razorpay payment attempt (success and failure)."""
    pending_order       = models.ForeignKey(RazorpayPendingOrder,
                                             on_delete=models.CASCADE,
                                             related_name="attempts",
                                             null=True, blank=True)
    user                = models.ForeignKey(settings.AUTH_USER_MODEL,
                                            on_delete=models.CASCADE,
                                            related_name="payment_attempts")
    razorpay_order_id   = models.CharField(max_length=120)
    razorpay_payment_id = models.CharField(max_length=120, blank=True, default="")
    amount              = models.FloatField()
    status              = models.CharField(max_length=12,
                                           choices=PaymentAttemptStatus.choices,
                                           default=PaymentAttemptStatus.INITIATED)
    failure_reason      = models.CharField(max_length=500, blank=True, default="")
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_attempts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.razorpay_order_id} — {self.status}"
