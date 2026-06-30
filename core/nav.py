ADMIN_NAV = [
    {"heading": "", "items": [
        {"label": "Dashboard", "href": "/admin-panel", "icon": "grid"}]},
    {"heading": "Catalog", "items": [
        {"label": "Products", "href": "/admin-panel/products", "icon": "package"},
        {"label": "Categories", "href": "/admin-panel/categories", "icon": "folder"},
        {"label": "Product Variants", "href": "/admin-panel/variants", "icon": "layers"},
        {"label": "Combo Packs", "href": "/admin-panel/combos", "icon": "gift"},
        {"label": "Inventory", "href": "/admin-panel/inventory", "icon": "box"}]},
    {"heading": "Orders", "items": [
        {"label": "All Orders", "href": "/admin-panel/orders", "icon": "bag", "count_key": "all"},
        {"label": "Pending", "href": "/admin-panel/orders?status=PROCESSING", "icon": "clock", "count_key": "pending"},
        {"label": "Processing", "href": "/admin-panel/orders?status=ORDER_CONFIRMED", "icon": "loader", "count_key": "processing"},
        {"label": "Shipped", "href": "/admin-panel/orders?status=DISPATCHED", "icon": "truck", "count_key": "shipped"},
        {"label": "Delivered", "href": "/admin-panel/orders?status=DELIVERED", "icon": "check-circle", "count_key": "delivered"},
        {"label": "Cancelled", "href": "/admin-panel/orders?status=CANCELLED", "icon": "x-circle", "count_key": "cancelled"},
        {"label": "Returns", "href": "/admin-panel/orders?status=REFUNDED", "icon": "rotate-ccw", "count_key": "returns"}]},
    {"heading": "Customers", "items": [
        {"label": "Customer List", "href": "/admin-panel/users", "icon": "users"},
        {"label": "Loyalty Members", "href": "/admin-panel/loyalty", "icon": "award"},
        {"label": "Reviews", "href": "/admin-panel/reviews", "icon": "star"}]},
    {"heading": "Marketing", "items": [
        {"label": "Coupons", "href": "/admin-panel/coupons", "icon": "percent"},
        {"label": "Banners", "href": "/admin-panel/banners", "icon": "image"},
        {"label": "Offers", "href": "/admin/store/homeoffer/", "icon": "tag"},
        {"label": "Newsletter", "href": "/admin/store/notification/", "icon": "mail"}]},
    {"heading": "Analytics", "items": [
        {"label": "Sales Reports", "href": "/admin-panel/reports", "icon": "chart"},
        {"label": "Revenue", "href": "/admin-panel/revenue", "icon": "trending-up"},
        {"label": "Performance", "href": "/admin-panel/performance", "icon": "activity"}]},
    {"heading": "Settings", "items": [
        {"label": "Settings",     "href": "/admin-panel/settings",     "icon": "settings"},
        {"label": "Integrations", "href": "/admin-panel/integrations", "icon": "plug"}]},
]
