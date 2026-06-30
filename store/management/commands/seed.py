"""
Seed command — faithful port of prisma/seed.ts.

Run:  python manage.py seed
Creates: admin + sample customer, 5 categories, 8 products with variants,
banners, blogs, testimonials, FAQs and policies. Idempotent.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User, UserType, Status
from core.utils import slugify
from store.models import (
    Banner, BannerType, Blog, Category, Faq, Policy, PolicyType, Product,
    ProductImage, ProductVariant, Review, ReviewStatus, Testimonial,
)


class Command(BaseCommand):
    help = "Seed the Spicearog database with demo data."

    def handle(self, *args, **opts):
        self.stdout.write("🌱 Seeding Spicearog…")

        # ---- Users ----
        admin, _ = User.objects.get_or_create(
            email="admin@spicearog.com",
            defaults=dict(first_name="Spicearog", last_name="Admin", mobile="9000000000",
                          user_type=UserType.ADMIN, status=Status.ACTIVE))
        admin.set_password("admin123")
        admin.user_type = UserType.ADMIN
        admin.save()

        priya, created = User.objects.get_or_create(
            email="priya@example.com",
            defaults=dict(first_name="Priya", last_name="Sharma", mobile="9876543210",
                          user_type=UserType.USER, status=Status.ACTIVE))
        if created:
            priya.set_password("user123")
            priya.save()
            priya.addresses.create(address_name="Home", address="12, Garden Street",
                                   city="Mumbai", pin_code="400001", is_default=True)

        # ---- Categories ----
        cats = [
            ("Spices", "/seed/cat-spices.jpg"),
            ("Masalas", "/seed/cat-masalas.jpg"),
            ("Herbs", "/seed/cat-herbs.jpg"),
            ("Dry Fruits", "/seed/cat-dryfruits.jpg"),
            ("Wellness", "/seed/cat-wellness.jpg"),
        ]
        cat_map = {}
        for i, (name, img) in enumerate(cats):
            c, _ = Category.objects.get_or_create(
                slug=slugify(name),
                defaults=dict(name=name, code=f"CAT{i+1}", image=img, position=i + 1))
            cat_map[name] = c

        # ---- Products ----
        products = [
            dict(name="Kashmiri Saffron", cat="Spices", badge="Bestseller", img="/seed/p-saffron.jpg",
                 featured=True,
                 desc="Hand-picked Kashmiri Mongra saffron with deep crimson threads, rich aroma and intense colour. Sun-dried and lab-tested for purity.",
                 variants=[("1g", 899, 1199), ("2g", 1699, 2199), ("5g", 3999, 4999)]),
            dict(name="Organic Turmeric Powder", cat="Masalas", badge="Organic", img="/seed/p-turmeric.jpg",
                 featured=True,
                 desc="Single-origin turmeric, cold-ground to preserve curcumin. Earthy, vibrant and 100% organic certified.",
                 variants=[("100g", 99, 149), ("250g", 199, 249), ("500g", 299, 399)]),
            dict(name="Ashwagandha Root Powder", cat="Wellness", badge="Wellness", img="/seed/p-ashwagandha.jpg",
                 featured=True,
                 desc="Pure ashwagandha root powder, traditionally used in Ayurveda to support calm, stamina and restful sleep.",
                 variants=[("100g", 199, 299), ("250g", 449, 549), ("500g", 799, 999)]),
            dict(name="Garam Masala Blend", cat="Masalas", badge="New", img="/seed/p-garam.jpg",
                 featured=True,
                 desc="A warming blend of 13 whole spices, roasted and stone-ground in small batches for an unmatched aroma.",
                 variants=[("50g", 99, 129), ("100g", 199, 249), ("250g", 449, 549)]),
            dict(name="Whole Black Pepper", cat="Spices", badge=None, img="/seed/p-pepper.jpg",
                 desc="Bold Malabar peppercorns with sharp heat and citrus notes. Estate sourced from the Western Ghats.",
                 variants=[("100g", 149, 199), ("250g", 329, 399)]),
            dict(name="Cardamom Pods", cat="Spices", badge="Organic", img="/seed/p-cardamom.jpg",
                 desc="Plump green cardamom pods bursting with sweet, floral fragrance — a kitchen and chai essential.",
                 variants=[("50g", 249, 299), ("100g", 449, 549)]),
            dict(name="Premium Cashews", cat="Dry Fruits", badge="Bestseller", img="/seed/p-cashew.jpg",
                 desc="Whole W240 grade cashews — buttery, crunchy and naturally processed with no additives.",
                 variants=[("250g", 299, 379), ("500g", 549, 699)]),
            dict(name="Holy Basil (Tulsi)", cat="Herbs", badge="Wellness", img="/seed/p-tulsi.jpg",
                 desc="Air-dried tulsi leaves prized in Ayurveda for immunity and respiratory wellness.",
                 variants=[("50g", 129, 179), ("100g", 229, 299)]),
        ]
        for i, p in enumerate(products):
            slug = slugify(p["name"])
            prod, made = Product.objects.get_or_create(
                slug=slug,
                defaults=dict(
                    name=p["name"], code=f"PRD{1000+i}", category=cat_map[p["cat"]],
                    description=p["desc"], image=p["img"], badge=p.get("badge"),
                    is_featured=bool(p.get("featured")),
                    top_seller=(p.get("badge") == "Bestseller"), position=i + 1))
            if made:
                ProductImage.objects.create(product=prod, image=p["img"])
                for vi, (v, sp, mrp) in enumerate(p["variants"]):
                    grams = float("".join(ch for ch in v if (ch.isdigit() or ch == ".")) or 0)
                    ProductVariant.objects.create(
                        product=prod, va_code=f"{slug}-{v}".upper(), variant=v, short_name=v,
                        selling_price=sp, mrp_price=mrp, stock=100, weight_in_gm=grams, position=vi + 1)
                if i == 0:
                    Review.objects.get_or_create(
                        user=priya, product=prod,
                        defaults=dict(rating=5, comment="Rich colour and aroma — truly authentic.",
                                      status=ReviewStatus.APPROVED))

        # ---- Banners ----
        if not Banner.objects.exists():
            Banner.objects.create(name="Taste the Purity of Nature's Finest",
                                  description="Handpicked spices, herbs & wellness products sourced directly from organic farms.",
                                  image="/seed/banner-hero.jpg", type=BannerType.HOME_BANNER, position=1)
            Banner.objects.create(name="Farm to Kitchen", image="/seed/banner-brand.jpg",
                                  video_url="https://www.w3schools.com/html/mov_bbb.mp4",
                                  type=BannerType.BRAND, position=1)
            Banner.objects.create(name="Our Organic Story", image="/seed/banner-brand2.jpg",
                                  video_url="https://www.w3schools.com/html/mov_bbb.mp4",
                                  type=BannerType.BRAND, position=2)

        # ---- Blogs ----
        blogs = [
            ("The Ancient Power of Turmeric in Modern Wellness", "Wellness",
             "Discover how this golden spice has been used for centuries in Ayurveda and how it integrates into your daily health routine."),
            ("From Farm to Your Kitchen: How We Source Our Spices", "Our Story",
             "A behind-the-scenes look at our partner farms in Kerala and the meticulous process of selecting only the finest ingredients."),
            ("5 Ayurvedic Morning Rituals Using Everyday Spices", "Lifestyle",
             "Simple, powerful habits using cinnamon, cardamom, and ginger that Ayurvedic practitioners have sworn by for thousands of years."),
            ("Why Cold-Ground Spices Retain More Flavour", "Wellness",
             "The science of preserving essential oils and nutrients through low-temperature grinding."),
            ("Building the Perfect Masala Dabba", "Lifestyle",
             "A starter guide to stocking your Indian spice box with the essentials."),
        ]
        for title, tag, desc in blogs:
            Blog.objects.get_or_create(slug=slugify(title),
                                       defaults=dict(title=title, tag=tag, description=desc, image="/seed/blog.jpg"))

        # ---- Testimonials ----
        if not Testimonial.objects.exists():
            Testimonial.objects.create(name="Meera Nair", city="Mumbai", rating=5, position=1,
                                       comment="The Kashmiri saffron is absolutely divine — rich colour and aroma. Spicearog is on another level. Truly authentic.")
            Testimonial.objects.create(name="Rajesh Gupta", city="Delhi", rating=5, position=2,
                                       comment="Their garam masala has completely transformed my cooking. The freshness is unmatched. My family keeps asking what changed!")
            Testimonial.objects.create(name="Ananya Sharma", city="Bangalore", rating=5, position=3,
                                       comment="Ashwagandha powder has been a game changer for my daily wellness routine. Clean, pure, and truly effective.")

        # ---- FAQ ----
        if not Faq.objects.exists():
            Faq.objects.create(question="Are your products 100% organic?",
                               answer="Yes. All Spicearog products are sourced from organic-certified partner farms and are FSSAI certified.", position=1)
            Faq.objects.create(question="How fast is delivery?",
                               answer="Orders are dispatched within 24-48 hours. Free delivery on orders above ₹499.", position=2)
            Faq.objects.create(question="What is your return policy?",
                               answer="Unopened products can be returned within 7 days of delivery.", position=3)

        # ---- Policies ----
        for ptype, title in [(PolicyType.ABOUT_US, "About Us"),
                             (PolicyType.TERMS, "Terms & Conditions"),
                             (PolicyType.PRIVACY, "Privacy Policy")]:
            Policy.objects.get_or_create(
                type=ptype,
                defaults=dict(title=title,
                              content=f"<h2>{title}</h2><p>Edit this content from the admin panel.</p>"))

        self.stdout.write(self.style.SUCCESS(
            "✅ Seed complete. Admin: admin@spicearog.com / admin123 — User: priya@example.com / user123"))
