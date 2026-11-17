"""SmartBite - AI-enabled online food delivery platform (Flask)."""
import os
import re
import secrets
import time
import uuid
import smtplib
from email.message import EmailMessage
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for)
from flask_login import (LoginManager, current_user, login_required, login_user, logout_user)
from markupsafe import Markup
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from config import Config
from models import (Ad, CartItem, Category, ContactMessage, Favorite, FoodItem, FraudFlag, Notification, Order,
                    OrderItem, Payment, PaymentProof, Restaurant, Review, RiderLocation, Setting, StaffMember, User, db, utcnow)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
Image.MAX_IMAGE_PIXELS = 40_000_000

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"
login_manager.session_protection = "basic"


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------
ROLE_HOME = {"customer": "customer_dashboard", "restaurant_owner": "owner_dashboard", "rider": "rider_dashboard",
             "admin": "admin_dashboard", "staff": "staff_dashboard"}
STATUS_LABEL = {"placed": "Placed", "confirmed": "Confirmed", "preparing": "Preparing",
                "out_for_delivery": "Out for delivery", "delivered": "Delivered", "cancelled": "Cancelled"}
PAY_LABEL = {"pending": "Payment pending", "awaiting_verification": "Verifying payment", "paid": "Paid",
             "rejected": "Payment rejected"}
DEFAULT_SETTINGS = {"commission_percent": "10", "service_charge": "100", "ad_price_per_week": "5000",
                    "rider_fee": "500", "admin_bank_name": "", "admin_account_name": "", "admin_account_number": "",
                    "contact_email": "", "contact_phone": "", "contact_address": ""}
DEFAULT_CATEGORIES = ["Rice Dishes", "Soups & Stews", "Grills & BBQ", "Fast Food", "Small Chops & Snacks", "Pasta",
                      "Seafood", "Breakfast", "Drinks", "Desserts"]
DEFAULT_IMG = {"food": "images/default-food.svg", "restaurant": "images/default-restaurant.svg",
               "avatar": "images/default-avatar.svg"}

NAV = {
    "customer": [("customer_dashboard", "Dashboard", "dashboard"), ("customer_browse_menu", "Browse Menu", "food"),
                 ("customer_restaurants", "Browse Restaurants", "store"),
                 ("customer_orders", "My Orders", "bag"), ("customer_favorites", "Favorites", "heart"),
                 ("customer_tracking", "Order Tracking", "truck"), ("profile", "Profile", "user"),
                 ("settings", "Settings", "settings")],
    "restaurant_owner": [("owner_dashboard", "Dashboard", "dashboard"), ("owner_foods", "My Foods", "food"),
                         ("owner_orders", "Incoming Orders", "bag"), ("owner_verifications", "Payment Verifications", "shield"),
                         ("owner_analytics", "Analytics", "chart"), ("owner_staff", "Staff", "users"),
                         ("owner_earnings", "Earnings", "wallet"), ("owner_ads", "Sponsored Ads", "megaphone"),
                         ("owner_profile", "Profile", "store"), ("settings", "Settings", "settings")],
    "rider": [("rider_dashboard", "Dashboard", "dashboard"), ("rider_available", "Available Orders", "bag"), ("rider_deliveries", "My Deliveries", "truck"),
              ("rider_map", "Route Map", "map"), ("rider_earnings", "Earnings", "wallet"),
              ("rider_history", "Delivery History", "list"), ("profile", "Profile", "user"),
              ("settings", "Settings", "settings")],
    "admin": [("admin_dashboard", "Dashboard Analytics", "dashboard"), ("admin_users", "Manage Users", "users"),
              ("admin_restaurants", "Manage Restaurants", "store"), ("admin_riders", "Manage Riders", "truck"),
              ("admin_orders", "All Orders", "bag"), ("admin_proofs", "All Payment Proofs", "shield"),
              ("admin_transactions", "Transactions", "wallet"), ("admin_categories", "Manage Categories", "tag"),
              ("admin_ads", "Sponsored Ads", "megaphone"), ("admin_fraud", "Fraud Alerts", "alert"),
              ("admin_messages", "Messages", "mail"), ("admin_settings", "Settings", "settings")],
    "staff": [("staff_dashboard", "Kitchen Queue", "bag"), ("staff_salary", "My Salary", "wallet"),
              ("profile", "Profile", "user"), ("settings", "Settings", "settings")],
}
NAV_ALIAS = {"customer_menu": "customer_browse_menu", "customer_order_detail": "customer_orders",
             "customer_search": "customer_dashboard", "customer_cart": "customer_dashboard",
             "customer_checkout": "customer_dashboard", "customer_payment": "customer_orders",
             "owner_food_form": "owner_foods", "notifications": None}

_P = {
    "dashboard": '<rect x="3" y="3" width="8" height="9" rx="1.5"/><rect x="13" y="3" width="8" height="5" rx="1.5"/><rect x="13" y="10" width="8" height="11" rx="1.5"/><rect x="3" y="14" width="8" height="7" rx="1.5"/>',
    "store": '<path d="M3 9l1-5h16l1 5"/><path d="M4 9v11h16V9"/><path d="M9 20v-6h6v6"/>',
    "bag": '<path d="M6 7h12l1 14H5z"/><path d="M9 7a3 3 0 016 0"/>',
    "heart": '<path d="M12 21s-8-5.2-8-11a4.5 4.5 0 018-2.8A4.5 4.5 0 0120 10c0 5.8-8 11-8 11z"/>',
    "truck": '<path d="M3 6h11v10H3z"/><path d="M14 9h4l3 3v4h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    "settings": '<path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    "logout": '<path d="M9 4H5v16h4"/><path d="M16 8l4 4-4 4M20 12H9"/>',
    "bell": '<path d="M6 17V11a6 6 0 0112 0v6l2 2H4z"/><path d="M10 21h4"/>',
    "cart": '<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l3 12h11l2-8H6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/>',
    "menu": '<path d="M3 6h18M3 12h18M3 18h18"/>',
    "chart": '<path d="M4 20V4M4 20h16"/><path d="M8 16v-4M13 16V8M18 16v-7"/>',
    "wallet": '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><circle cx="16" cy="14.5" r="1"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5"/><circle cx="17" cy="9" r="2.5"/><path d="M17 14c3 0 5 1.5 5 4.5"/>',
    "tag": '<path d="M3 12V3h9l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
    "alert": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>',
    "megaphone": '<path d="M3 10v4h4l8 5V5L7 10z"/><path d="M18 9a4 4 0 010 6"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
    "map": '<path d="M12 21s-7-6-7-11a7 7 0 0114 0c0 5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "edit": '<path d="M4 20h4L20 8l-4-4L4 16z"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "sparkle": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16v4M17 18h4"/>',
    "flame": '<path d="M12 3c1 4 5 5 5 10a5 5 0 01-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 1-9z"/>',
    "upload": '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 20h16"/>',
    "food": '<path d="M7 3v8M4 3v5a3 3 0 006 0V3M7 11v10"/><path d="M17 3c-2 2-3 5-3 8h3v10"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/>',
    "pin": '<path d="M12 21s-7-6-7-11a7 7 0 0114 0c0 5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "moon": '<path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
}


def icon(name, size=20):
    body = _P.get(name, _P["info"])
    return Markup(f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
                  f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
                  f'aria-hidden="true">{body}</svg>')


# --------------------------------------------------------------------------------------
# Security: CSRF, headers, throttling
# --------------------------------------------------------------------------------------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(32)
    return session["_csrf"]


def wants_json():
    return request.is_json or request.headers.get("X-Requested-With") == "fetch"


@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or ""
        expected = session.get("_csrf", "")
        if not expected or not secrets.compare_digest(sent.encode("utf-8"), expected.encode("utf-8")):
            if wants_json():
                return jsonify(ok=False, message="Your session expired. Refresh the page and try again."), 400
            flash("Your session expired. Please try again.", "error")
            return redirect(url_for("index"))


@app.before_request
def force_password_change():
    if (current_user.is_authenticated and current_user.must_change_password and request.endpoint
            and request.endpoint not in ("settings", "change_password", "logout", "static", "api_unread")):
        if wants_json():
            return jsonify(ok=False, message="Change your password first."), 403
        flash("For your security, set a new password before continuing.", "info")
        return redirect(url_for("settings", tab="password"))


CSP = ("default-src 'self'; "
       "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com https://js.paystack.co; "
       "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com data:; "
       "img-src 'self' data: blob: https://*.tile.openstreetmap.org https://unpkg.com; "
       "connect-src 'self' https://nominatim.openstreetmap.org https://router.project-osrm.org https://*.paystack.co; "
       "frame-src https://checkout.paystack.com https://*.paystack.co; "
       "form-action 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'")


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    resp.headers["Content-Security-Policy"] = CSP
    if app.config["SESSION_COOKIE_SECURE"]:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.endpoint != "static" and resp.mimetype == "text/html":
        resp.headers["Cache-Control"] = "no-store"
    return resp


_ATTEMPTS = defaultdict(list)


def throttled(key, limit=5, window=300, record=False):
    """Simple in-memory rate limiter. Use a shared store (Redis) if you run several workers."""
    now = time.time()
    _ATTEMPTS[key] = [t for t in _ATTEMPTS[key] if now - t < window]
    if record:
        _ATTEMPTS[key].append(now)
    return len(_ATTEMPTS[key]) >= limit


def is_safe_url(target):
    if not target:
        return False
    ref, test = urlparse(request.host_url), urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


def back(default_endpoint, **values):
    target = request.referrer
    if target and is_safe_url(target):
        return redirect(target)
    return redirect(url_for(default_endpoint, **values))


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# --------------------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------------------
def get_setting(key, cast=str):
    row = db.session.get(Setting, key)
    value = row.setting_value if row and row.setting_value is not None else DEFAULT_SETTINGS.get(key, "")
    try:
        return cast(value) if value != "" else cast(0) if cast in (int, float) else ""
    except (TypeError, ValueError):
        return cast(0) if cast in (int, float) else ""


def set_setting(key, value):
    row = db.session.get(Setting, key)
    if row:
        row.setting_value = str(value)
    else:
        db.session.add(Setting(setting_key=key, setting_value=str(value)))


def get_float(key):
    return get_setting(key, float)


def get_int(key):
    return int(get_setting(key, float))


def img_url(path, kind="food"):
    return url_for("static", filename=path or DEFAULT_IMG[kind])


def page_url(page):
    args = request.args.to_dict()
    args["page"] = page
    return url_for(request.endpoint, **args)


def to_int(value, default=0, low=None, high=None):
    try:
        number = int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default
    if low is not None:
        number = max(low, number)
    if high is not None:
        number = min(high, number)
    return number


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean(value, limit=255):
    return re.sub(r"\s+", " ", (value or "").strip())[:limit]


def clean_block(value, limit=2000):
    return (value or "").strip()[:limit]


def valid_email(email):
    return bool(re.fullmatch(r"[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}", email or "")) and len(email) <= 100


def valid_phone(phone):
    return bool(re.fullmatch(r"\+?[0-9 ()-]{7,20}", phone or ""))


def password_problem(pw):
    if len(pw or "") < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must contain at least one letter and one number."
    return None


def save_image(file, folder="uploads", max_px=1200):
    """Validate an uploaded JPG/PNG, strip metadata, resize and store it. Returns path relative to /static."""
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("jpg", "jpeg", "png"):
        raise ValueError("Only JPG or PNG images are allowed.")
    try:
        probe = Image.open(file.stream)
        probe.verify()
        file.stream.seek(0)
        img = Image.open(file.stream)
        fmt = img.format
        if fmt not in ("JPEG", "PNG"):
            raise ValueError("Only JPG or PNG images are allowed.")
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_px, max_px))
        target_dir = os.path.join(app.static_folder, folder)
        os.makedirs(target_dir, exist_ok=True)
        if fmt == "PNG":
            name = uuid.uuid4().hex + ".png"
            img.save(os.path.join(target_dir, name), "PNG", optimize=True)
        else:
            name = uuid.uuid4().hex + ".jpg"
            img.convert("RGB").save(os.path.join(target_dir, name), "JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ValueError("That file is not a valid image.")
    return f"{folder}/{name}"


def delete_image(rel_path):
    if not rel_path or not rel_path.startswith("uploads/"):
        return
    root = os.path.realpath(os.path.join(app.static_folder, "uploads"))
    full = os.path.realpath(os.path.join(app.static_folder, rel_path))
    if full.startswith(root + os.sep) and os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass


def upload_or_flash(field, folder="uploads", max_px=1200):
    """Returns (path, error). path is None when no file was sent."""
    file = request.files.get(field)
    if not file or not file.filename:
        return None, None
    try:
        return save_image(file, folder, max_px), None
    except ValueError as exc:
        return None, str(exc)


def notify(user_id, title, message="", link=None):
    db.session.add(Notification(user_id=user_id, title=title[:150], message=(message or "")[:500], link=link))


def notify_admins(title, message="", link=None):
    for admin in User.query.filter_by(role="admin", active=True).all():
        notify(admin.id, title, message, link)


def calc_totals(subtotal):
    pct = get_float("commission_percent")
    service = get_int("service_charge")
    commission = int(round(subtotal * pct / 100.0))
    return {"subtotal": subtotal, "service_charge": service, "commission": commission, "pct": pct,
            "total": subtotal + service + commission}


def live_ad_restaurant_ids():
    now = utcnow()
    rows = Ad.query.filter(Ad.status == "approved", Ad.starts_at <= now, Ad.ends_at >= now).all()
    return {a.restaurant_id for a in rows}


def sponsored_first(restaurants):
    ids = live_ad_restaurant_ids()
    return sorted(restaurants, key=lambda r: (r.id not in ids, -(r.rating or 0), r.name.lower())), ids


def as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def last_days(n):
    today = utcnow().date()
    return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]


def series_by_day(rows, days):
    """rows: iterable of (date-like, number) -> list of numbers aligned to `days`."""
    totals = defaultdict(float)
    for d, v in rows:
        totals[as_date(d)] += float(v or 0)
    return [round(totals.get(d, 0), 2) for d in days]


def role_home(user):
    return url_for(ROLE_HOME.get(user.role, "index"))


def time_ago(value):
    if not value:
        return ""
    seconds = int((utcnow() - value).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} hr ago"
    if seconds < 7 * 86400:
        return f"{seconds // 86400} d ago"
    return value.strftime("%d %b %Y")


app.jinja_env.globals.update(icon=icon, csrf_token=csrf_token, img_url=img_url, page_url=page_url)
app.jinja_env.filters["naira"] = lambda v: "\u20a6{:,}".format(int(v or 0))
app.jinja_env.filters["dt"] = lambda v: v.strftime("%d %b %Y, %H:%M") if v else ""
app.jinja_env.filters["dday"] = lambda v: v.strftime("%d %b %Y") if v else ""
app.jinja_env.filters["ago"] = time_ago
app.jinja_env.filters["status_label"] = lambda s: STATUS_LABEL.get(s, s)
app.jinja_env.filters["pay_label"] = lambda s: PAY_LABEL.get(s, s)


def delivery_eta(order):
    """Return a practical, clearly approximate remaining delivery window."""
    if order.status == "delivered":
        return "Delivered"
    if order.status == "cancelled":
        return "Not available for cancelled orders"
    if order.status == "out_for_delivery":
        return "About 10–25 minutes (rider is on the way)"
    if order.status == "preparing":
        return "About 20–35 minutes (being prepared)"
    if order.status == "confirmed":
        return "About 30–45 minutes"
    return "About 35–55 minutes after order confirmation"


@app.context_processor
def inject_globals():
    ctx = {"delivery_eta": delivery_eta, "app_name": "SmartBite", "nav_items": [], "nav_alias": NAV_ALIAS, "cart_count": 0, "unread_count": 0,
           "my_restaurant": None, "home_url": url_for("index"), "paystack_key": app.config["PAYSTACK_PUBLIC_KEY"], "year": utcnow().year}
    if current_user.is_authenticated:
        ctx["nav_items"] = NAV.get(current_user.role, [])
        ctx["home_url"] = role_home(current_user)
        ctx["unread_count"] = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        if current_user.role == "customer":
            ctx["cart_count"] = db.session.query(func.coalesce(func.sum(CartItem.quantity), 0)) \
                .filter(CartItem.customer_id == current_user.id).scalar() or 0
        elif current_user.role == "restaurant_owner":
            ctx["my_restaurant"] = current_user.restaurant
    return ctx


# --------------------------------------------------------------------------------------
# AI features
# --------------------------------------------------------------------------------------
_STOP = {"under", "below", "less", "than", "over", "above", "more", "at", "least", "between", "and", "to", "the", "a",
         "an", "for", "with", "me", "show", "find", "i", "want", "need", "some", "cheap", "good", "best", "around",
         "within", "max", "maximum", "min", "minimum", "price", "of", "in", "naira", "ngn", "budget", "please",
         "not", "exceeding", "up", "k", "food", "foods"}
_NUM = r"₦?\s*([0-9][0-9,]*(?:\.[0-9]+)?k?)"


def _to_price(text):
    text = text.replace(",", "").replace(" ", "").lower()
    mult = 1000 if text.endswith("k") else 1
    try:
        return int(float(text.rstrip("k")) * mult)
    except ValueError:
        return None


def parse_query(q):
    """AI 2 - Smart Search. 'spicy chicken under 3000' -> terms [spicy, chicken], max price 3000."""
    text = (q or "").lower().strip()[:120]
    parsed = {"terms": [], "min": None, "max": None, "min_inclusive": False, "max_inclusive": False, "raw": q or ""}
    m = re.search(r"between\s*" + _NUM + r"\s*(?:and|to|-)\s*" + _NUM, text)
    if m:
        lo, hi = _to_price(m.group(1)), _to_price(m.group(2))
        if lo is not None and hi is not None:
            parsed["min"], parsed["max"] = min(lo, hi), max(lo, hi)
            parsed["min_inclusive"] = parsed["max_inclusive"] = True
        text = text.replace(m.group(0), " ")
    m = re.search(r"(?:under|below|less than|cheaper than|within|max(?:imum)?|not more than|up to|not exceeding|<=?)\s*" + _NUM, text)
    if m:
        parsed["max"] = _to_price(m.group(1))
        parsed["max_inclusive"] = False
        text = text.replace(m.group(0), " ")
    m = re.search(r"(?:over|above|more than|at least|min(?:imum)?|>=?)\s*" + _NUM, text)
    if m:
        parsed["min"] = _to_price(m.group(1))
        parsed["min_inclusive"] = False
        text = text.replace(m.group(0), " ")
    parsed["terms"] = [t for t in re.findall(r"[a-z]+", text) if t not in _STOP and len(t) > 1][:6]
    return parsed


def smart_search(q, limit=40):
    parsed = parse_query(q)

    def run(match_all):
        query = FoodItem.query.join(Restaurant, Restaurant.id == FoodItem.restaurant_id) \
            .filter(Restaurant.is_approved.is_(True), FoodItem.is_available.is_(True))
        if parsed["max"] is not None:
            query = query.filter(FoodItem.price <= parsed["max"] if parsed["max_inclusive"] else FoodItem.price < parsed["max"])
        if parsed["min"] is not None:
            query = query.filter(FoodItem.price >= parsed["min"] if parsed["min_inclusive"] else FoodItem.price > parsed["min"])
        clauses = []
        for term in parsed["terms"]:
            like = f"%{term}%"
            clauses.append(or_(FoodItem.name.ilike(like), FoodItem.description.ilike(like),
                               FoodItem.category.ilike(like), Restaurant.name.ilike(like)))
        if clauses:
            query = query.filter(*clauses) if match_all else query.filter(or_(*clauses))
        return query.order_by(Restaurant.rating.desc(), FoodItem.price.asc()).limit(limit).all()

    foods, relaxed = run(True), False
    if not foods and len(parsed["terms"]) > 1:
        foods, relaxed = run(False), True
    restaurants = []
    if parsed["terms"]:
        rq = Restaurant.query.filter(Restaurant.is_approved.is_(True))
        for term in parsed["terms"]:
            like = f"%{term}%"
            rq = rq.filter(or_(Restaurant.name.ilike(like), Restaurant.description.ilike(like)))
        restaurants = rq.limit(12).all()
    return {"foods": foods, "restaurants": restaurants, "parsed": parsed, "relaxed": relaxed, "q": q or ""}


def _foods_in_order(rows):
    """rows: [(food_id, qty)] -> [(FoodItem, qty)] in the same order, available + approved only."""
    ids = [r[0] for r in rows if r[0]]
    if not ids:
        return []
    foods = FoodItem.query.join(Restaurant, Restaurant.id == FoodItem.restaurant_id) \
        .filter(FoodItem.id.in_(ids), FoodItem.is_available.is_(True), Restaurant.is_approved.is_(True)).all()
    by_id = {f.id: f for f in foods}
    return [(by_id[fid], qty) for fid, qty in rows if fid in by_id]


def popular_foods(since=None, restaurant_ids=None, limit=6):
    q = db.session.query(OrderItem.food_id, func.sum(OrderItem.quantity).label("qty")) \
        .join(Order, Order.id == OrderItem.order_id) \
        .filter(Order.status != "cancelled", OrderItem.food_id.isnot(None))
    if since is not None:
        q = q.filter(Order.created_at >= since)
    if restaurant_ids is not None:
        q = q.filter(Order.restaurant_id.in_(list(restaurant_ids) or [0]))
    rows = q.group_by(OrderItem.food_id).order_by(func.sum(OrderItem.quantity).desc()).limit(limit * 3).all()
    return _foods_in_order([(r[0], int(r[1] or 0)) for r in rows])[:limit]


def recommend_for(user, limit=6):
    """AI 1 - Food recommendation from the customer's own order history."""
    rows = db.session.query(OrderItem.food_id, func.count(OrderItem.id).label("c"), func.sum(OrderItem.quantity)) \
        .join(Order, Order.id == OrderItem.order_id) \
        .filter(Order.customer_id == user.id, Order.status != "cancelled", OrderItem.food_id.isnot(None)) \
        .group_by(OrderItem.food_id) \
        .order_by(func.count(OrderItem.id).desc(), func.sum(OrderItem.quantity).desc()).limit(limit * 2).all()
    picks = _foods_in_order([(r[0], int(r[1])) for r in rows])[:limit]
    if picks:
        return picks, "Based on your past orders"
    return popular_foods(limit=limit), "Popular on SmartBite right now"


_GENERIC = {"street", "road", "avenue", "close", "estate", "drive", "lane", "crescent", "behind", "opposite", "beside",
            "along", "house", "plot", "block", "flat", "floor", "near", "junction", "bus", "stop"}


def nearby_restaurant_ids(address):
    tokens = {t for t in re.findall(r"[a-z0-9]+", (address or "").lower()) if len(t) > 3 and t not in _GENERIC}
    if not tokens:
        return None
    ids = []
    for r in Restaurant.query.filter(Restaurant.is_approved.is_(True)).all():
        words = set(re.findall(r"[a-z0-9]+", (r.address or "").lower()))
        if tokens & words:
            ids.append(r.id)
    return ids or None


def ai_picks(user):
    """AI 3 - most ordered today, and trending near the customer."""
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    top_today = popular_foods(since=today_start, limit=6)
    today_label = "Most ordered today"
    if not top_today:
        top_today, today_label = popular_foods(since=utcnow() - timedelta(days=7), limit=6), "Most ordered this week"
    near_ids = nearby_restaurant_ids(user.address)
    trending = popular_foods(since=utcnow() - timedelta(days=7), restaurant_ids=near_ids, limit=6) if near_ids else []
    trend_label = "Trending near you"
    if not trending:
        trending, trend_label = popular_foods(since=utcnow() - timedelta(days=14), limit=6), "Trending on SmartBite"
    return {"today": top_today, "today_label": today_label, "trending": trending, "trend_label": trend_label}


def demand_forecast(restaurant_id):
    """AI 4 - forecast tomorrow's demand per dish from the last 28 days of sales."""
    today = utcnow().date()
    start = today - timedelta(days=27)
    rows = db.session.query(OrderItem.food_name, func.date(Order.created_at), func.sum(OrderItem.quantity)) \
        .join(Order, Order.id == OrderItem.order_id) \
        .filter(Order.restaurant_id == restaurant_id, Order.status != "cancelled",
                Order.created_at >= datetime.combine(start, datetime.min.time())) \
        .group_by(OrderItem.food_name, func.date(Order.created_at)).all()
    per_food = defaultdict(lambda: defaultdict(float))
    for name, day, qty in rows:
        per_food[name][as_date(day)] += float(qty or 0)
    tomorrow = today + timedelta(days=1)
    forecasts = []
    for name, series in per_food.items():
        if sum(series.values()) < 3:
            continue
        recent = sum(series.get(today - timedelta(days=i), 0) for i in range(7)) / 7.0
        same_dow = [series.get(tomorrow - timedelta(days=7 * k), 0) for k in range(1, 5)]
        dow_avg = sum(same_dow) / len(same_dow)
        expected = 0.6 * dow_avg + 0.4 * recent if dow_avg > 0 else recent
        pct = round((expected - recent) / recent * 100) if recent > 0 else 0
        if pct >= 5:
            text = f"Expect +{pct}% more {name} tomorrow"
        elif pct <= -5:
            text = f"Expect {abs(pct)}% less {name} tomorrow"
        else:
            text = f"Steady demand for {name} tomorrow (about {max(1, round(expected))} portions)"
        forecasts.append({"name": name, "expected": round(expected, 1), "pct": pct, "text": text})
    forecasts.sort(key=lambda f: f["expected"], reverse=True)

    days = last_days(14)
    totals = defaultdict(float)
    for series in per_food.values():
        for d, q in series.items():
            totals[d] += q
    actual = [round(totals.get(d, 0), 1) for d in days]
    labels = [d.strftime("%d %b") for d in days] + [tomorrow.strftime("%d %b") + " (forecast)"]
    chart = {"type": "bar", "overlap": True, "labels": labels,
             "datasets": [{"label": "Portions sold", "data": actual + [None], "color": "#FF8C42"},
                          {"label": "Forecast", "data": [None] * 14 + [round(sum(f["expected"] for f in forecasts), 1)],
                           "color": "#4CAF7D"}]}
    return forecasts[:8], chart


def run_fraud_checks(order):
    """AI 6 - flag >5 orders in 10 minutes by one customer, or any order above 50,000."""
    reasons = []
    window = order.created_at - timedelta(minutes=10)
    count = Order.query.filter(Order.customer_id == order.customer_id, Order.created_at >= window,
                               Order.created_at <= order.created_at).count()
    if count > 5:
        reasons.append(f"{count} orders placed within 10 minutes")
    if order.total_amount > 50000:
        reasons.append(f"High-value order of \u20a6{order.total_amount:,}")
    for reason in reasons:
        db.session.add(FraudFlag(order_id=order.id, user_id=order.customer_id, reason=reason))
    if reasons:
        notify_admins("Possible fraud detected", f"Order #{order.id}: " + "; ".join(reasons), url_for("admin_fraud"))
    return reasons


def scan_all_orders_for_fraud():
    """Re-scan every order with a sliding 10-minute window. Returns number of new flags."""
    existing = {(f.order_id, f.reason) for f in FraudFlag.query.all()}
    created = 0
    orders = Order.query.order_by(Order.customer_id, Order.created_at).all()
    by_customer = defaultdict(list)
    for o in orders:
        by_customer[o.customer_id].append(o)
    for customer_orders in by_customer.values():
        for idx, o in enumerate(customer_orders):
            reasons = []
            window = [x for x in customer_orders[:idx + 1] if (o.created_at - x.created_at) <= timedelta(minutes=10)]
            if len(window) > 5:
                reasons.append(f"{len(window)} orders placed within 10 minutes")
            if o.total_amount > 50000:
                reasons.append(f"High-value order of \u20a6{o.total_amount:,}")
            for reason in reasons:
                if (o.id, reason) not in existing:
                    db.session.add(FraudFlag(order_id=o.id, user_id=o.customer_id, reason=reason))
                    existing.add((o.id, reason))
                    created += 1
    return created


# --------------------------------------------------------------------------------------
# Public pages and authentication
# --------------------------------------------------------------------------------------
@app.route("/")
def index():
    restaurants = Restaurant.query.filter_by(is_approved=True).order_by(Restaurant.rating.desc()).limit(30).all()
    ordered, ad_ids = sponsored_first(restaurants)
    popular = [f for f, _ in popular_foods(limit=8)]
    if len(popular) < 4:
        extra = FoodItem.query.join(Restaurant, Restaurant.id == FoodItem.restaurant_id) \
            .filter(Restaurant.is_approved.is_(True), FoodItem.is_available.is_(True)) \
            .order_by(FoodItem.created_at.desc()).limit(8).all()
        popular += [f for f in extra if f not in popular][:8 - len(popular)]
    testimonials = Review.query.filter(Review.rating >= 4, func.length(Review.comment) > 15) \
        .order_by(Review.created_at.desc()).limit(3).all()
    categories = Category.query.order_by(Category.name).all()
    contact = {k: get_setting(k) for k in ("contact_email", "contact_phone", "contact_address")}
    return render_template("index.html", featured=ordered[:6], ad_ids=ad_ids, popular=popular[:8],
                           testimonials=testimonials, categories=categories, contact=contact)


@app.route("/explore")
def explore():
    q = clean(request.args.get("q"), 120)
    results = smart_search(q) if q else None
    return render_template("explore.html", q=q, results=results)


@app.route("/contact", methods=["POST"])
def contact():
    name, email, message = clean(request.form.get("name"), 100), clean(request.form.get("email"), 100).lower(), \
        clean_block(request.form.get("message"), 2000)
    if throttled(f"contact|{request.remote_addr}", limit=5, window=3600, record=True):
        flash("You have sent several messages already. Please try again later.", "error")
    elif not name or not valid_email(email) or len(message) < 10:
        flash("Please enter your name, a valid email and a message of at least 10 characters.", "error")
    else:
        db.session.add(ContactMessage(name=name, email=email, message=message))
        notify_admins("New contact message", f"From {name}", url_for("admin_messages"))
        db.session.commit()
        flash("Thanks! Your message has been sent. We will reply by email.", "success")
    return redirect(url_for("index") + "#contact")


_DUMMY_HASH = generate_password_hash("smartbite-dummy-password")


def password_reset_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="smartbite-password-reset")


def send_password_reset_email(user, reset_url):
    """Send a short-lived password reset link when SMTP is configured."""
    host = os.environ.get("MAIL_SERVER", "").strip()
    sender = os.environ.get("MAIL_DEFAULT_SENDER", "").strip()
    if not host or not sender:
        return False
    message = EmailMessage()
    message["Subject"] = "Reset your SmartBite password"
    message["From"] = sender
    message["To"] = user.email
    message.set_content(
        f"Hello {user.name},\n\nWe received a request to reset your SmartBite password. "
        f"Use the link below within 30 minutes:\n\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n\nSmartBite Support"
    )
    port = int(os.environ.get("MAIL_PORT", "587"))
    username = os.environ.get("MAIL_USERNAME", "").strip()
    password = os.environ.get("MAIL_PASSWORD", "")
    use_tls = os.environ.get("MAIL_USE_TLS", "1").strip().lower() in ("1", "true", "yes", "on")
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)
    return True


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(role_home(current_user))
    if request.method == "POST":
        throttle_key = f"password-reset|{request.remote_addr}"
        if throttled(throttle_key, limit=3, window=900, record=True):
            flash("If the account exists, reset instructions will be sent when available. Please wait before trying again.", "info")
            return redirect(url_for("login"))
        email = clean(request.form.get("email"), 100).lower()
        user = User.query.filter_by(email=email).first() if valid_email(email) else None
        # Always use the same response so the page does not reveal registered accounts.
        if user and user.active:
            token = password_reset_serializer().dumps({"uid": user.id, "pw": user.password_hash})
            reset_url = url_for("reset_password", token=token, _external=True)
            try:
                sent = send_password_reset_email(user, reset_url)
            except Exception:
                app.logger.exception("Could not send SmartBite password reset email")
                sent = False
            if not sent:
                app.logger.warning("Password reset email could not be delivered; verify SMTP configuration.")
        flash("If an account exists for that email, password reset instructions will be sent. The link expires in 30 minutes.", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(role_home(current_user))
    try:
        payload = password_reset_serializer().loads(token, max_age=1800)
        user_id = payload.get("uid")
    except SignatureExpired:
        flash("That password reset link has expired. Request a new one.", "error")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("That password reset link is invalid. Request a new one.", "error")
        return redirect(url_for("forgot_password"))
    user = db.session.get(User, int(user_id))
    if not user or not user.active or payload.get("pw") != user.password_hash:
        flash("This password reset link is no longer valid.", "error")
        return redirect(url_for("forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        problem = password_problem(password)
        if problem:
            flash(problem, "error")
        elif password != confirm:
            flash("The passwords do not match.", "error")
        else:
            user.password_hash = generate_password_hash(password)
            user.must_change_password = False
            db.session.commit()
            flash("Your password has been reset. You can now log in.", "success")
            return redirect(url_for("login"))
    return render_template("reset_password.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(role_home(current_user))
    email = clean(request.values.get("email"), 100).lower()
    failed = False
    if request.method == "POST":
        password = request.form.get("password", "")
        key = f"login|{request.remote_addr}|{email}"
        if throttled(key):
            flash("Too many failed attempts. Please wait 5 minutes and try again.", "error")
            return render_template("login.html", email=email), 429
        user = User.query.filter_by(email=email).first()
        valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password)
        if user and valid:
            if not user.active:
                flash("This account has been deactivated. Please contact support.", "error")
                return render_template("login.html", email=email)
            _ATTEMPTS.pop(key, None)
            session.clear()
            session.permanent = True
            login_user(user, remember=bool(request.form.get("remember")))
            flash(f"Welcome back, {user.name.split()[0]}!", "success")
            target = request.form.get("next") or request.args.get("next")
            return redirect(target if is_safe_url(target) else role_home(user))
        throttled(key, record=True)
        failed = True
        flash("Invalid email or password.", "error")
    return render_template("login.html", email=email, failed=failed, next=request.args.get("next", ""))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(role_home(current_user))
    form = {k: clean(request.form.get(k), 255) for k in ("name", "email", "phone", "address", "role", "restaurant_name")}
    if request.method == "GET":
        form["email"] = clean(request.args.get("email"), 100).lower()
        form["role"] = request.args.get("role") if request.args.get("role") in ("customer", "restaurant_owner", "rider") else "customer"
    if request.method == "POST":
        form["email"] = form["email"].lower()
        password, confirm = request.form.get("password", ""), request.form.get("confirm", "")
        error = None
        if throttled(f"signup|{request.remote_addr}", limit=10, window=3600, record=True):
            error = "Too many sign-ups from this network. Please try later."
        elif len(form["name"]) < 2:
            error = "Please enter your full name."
        elif not valid_email(form["email"]):
            error = "Please enter a valid email address."
        elif not valid_phone(form["phone"]):
            error = "Please enter a valid phone number."
        elif len(form["address"]) < 5:
            error = "Please enter your address."
        elif form["role"] not in ("customer", "restaurant_owner", "rider"):
            error = "Please choose how you will use SmartBite."
        elif form["role"] == "restaurant_owner" and len(form["restaurant_name"]) < 2:
            error = "Please enter your restaurant name."
        elif password_problem(password):
            error = password_problem(password)
        elif password != confirm:
            error = "The two passwords do not match."
        elif User.query.filter_by(email=form["email"]).first():
            error = "An account with this email already exists. Log in instead."
        image_path = None
        if not error:
            image_path, error = upload_or_flash("profile_image", "uploads", 600)
        if error:
            flash(error, "error")
            return render_template("signup.html", form=form), 400
        user = User(name=form["name"], email=form["email"], phone=form["phone"], address=form["address"],
                    role=form["role"], profile_image=image_path, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.flush()
        if user.role == "restaurant_owner":
            db.session.add(Restaurant(owner_id=user.id, name=form["restaurant_name"], address=user.address,
                                      phone=user.phone, status="pending", is_approved=False))
            notify_admins("New restaurant awaiting approval", f"{form['restaurant_name']} has registered.",
                          url_for("admin_restaurants", status="pending"))
        db.session.commit()
        session.clear()
        session.permanent = True
        login_user(user)
        flash("Your account is ready. Welcome to SmartBite!", "success")
        if user.role == "restaurant_owner":
            flash("Add your menu and bank details while we review your restaurant.", "info")
        return redirect(role_home(user))
    return render_template("signup.html", form=form)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# --------------------------------------------------------------------------------------
# Shared pages: notifications, profile, settings
# --------------------------------------------------------------------------------------
@app.route("/notifications")
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(100).all()
    unread_ids = {n.id for n in items if not n.is_read}
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("shared/notifications.html", items=items, unread_ids=unread_ids)


@app.route("/notifications/clear", methods=["POST"])
@login_required
def notifications_clear():
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash("Notifications cleared.", "success")
    return redirect(url_for("notifications"))


@app.route("/api/notifications/unread")
@login_required
def api_unread():
    q = Notification.query.filter_by(user_id=current_user.id, is_read=False)
    latest = q.order_by(Notification.id.desc()).first()
    return jsonify(count=q.count(), latest_id=latest.id if latest else 0,
                   latest_title=latest.title if latest else "")


@app.route("/profile")
@login_required
def profile():
    if current_user.role == "restaurant_owner":
        return redirect(url_for("owner_profile"))
    stats = []
    if current_user.role == "customer":
        stats = [("Orders placed", Order.query.filter_by(customer_id=current_user.id).count()),
                 ("Favorites", Favorite.query.filter_by(user_id=current_user.id).count()),
                 ("Reviews written", Review.query.filter_by(customer_id=current_user.id).count())]
    elif current_user.role == "rider":
        done = Order.query.filter_by(rider_id=current_user.id, status="delivered")
        stats = [("Deliveries completed", done.count()),
                 ("Total earned", "\u20a6{:,}".format(db.session.query(func.coalesce(func.sum(Order.rider_fee), 0))
                                                       .filter(Order.rider_id == current_user.id, Order.status == "delivered").scalar()))]
    elif current_user.role == "staff" and current_user.staff_profile:
        stats = [("Position", current_user.staff_profile.staff_role.title()),
                 ("Restaurant", current_user.staff_profile.restaurant.name)]
    return render_template("shared/profile.html", stats=stats)


@app.route("/settings")
@login_required
def settings():
    tab = request.args.get("tab", "appearance")
    if tab not in ("appearance", "profile", "account", "password"):
        tab = "appearance"
    return render_template("shared/settings.html", tab=tab)


@app.route("/settings/profile", methods=["POST"])
@login_required
def update_profile():
    name, phone, address = clean(request.form.get("name"), 100), clean(request.form.get("phone"), 20), \
        clean_block(request.form.get("address"), 500)
    if len(name) < 2 or not valid_phone(phone) or (current_user.role in ("customer", "restaurant_owner") and len(address) < 5):
        flash("Please enter a valid name, phone number and address.", "error")
        return redirect(url_for("settings", tab="profile"))
    path, error = upload_or_flash("profile_image", "uploads", 600)
    if error:
        flash(error, "error")
        return redirect(url_for("settings", tab="profile"))
    if path:
        delete_image(current_user.profile_image)
        current_user.profile_image = path
    current_user.name, current_user.phone, current_user.address = name, phone, address
    db.session.commit()
    flash("Profile updated.", "success")
    return redirect(url_for("settings", tab="profile"))


@app.route("/settings/account", methods=["POST"])
@login_required
def update_account():
    email = clean(request.form.get("email"), 100).lower()
    if not check_password_hash(current_user.password_hash, request.form.get("current_password", "")):
        flash("Your current password is incorrect.", "error")
    elif not valid_email(email):
        flash("Please enter a valid email address.", "error")
    elif User.query.filter(User.email == email, User.id != current_user.id).first():
        flash("That email is already used by another account.", "error")
    else:
        current_user.email = email
        db.session.commit()
        flash("Account details updated.", "success")
    return redirect(url_for("settings", tab="account"))


@app.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    current, new, confirm = request.form.get("current_password", ""), request.form.get("new_password", ""), \
        request.form.get("confirm_password", "")
    problem = password_problem(new)
    if not check_password_hash(current_user.password_hash, current):
        flash("Your current password is incorrect.", "error")
    elif problem:
        flash(problem, "error")
    elif new != confirm:
        flash("The new passwords do not match.", "error")
    elif new == current:
        flash("Choose a password you have not used before.", "error")
    else:
        current_user.password_hash = generate_password_hash(new)
        current_user.must_change_password = False
        db.session.commit()
        flash("Password changed.", "success")
        return redirect(url_for("admin_settings") if current_user.role == "admin" else url_for("settings", tab="password"))
    return redirect(url_for("admin_settings") if current_user.role == "admin" else url_for("settings", tab="password"))


# --------------------------------------------------------------------------------------
# Payment proof review (restaurant owner + admin)
# --------------------------------------------------------------------------------------
@app.route("/proofs/<int:proof_id>/decide", methods=["POST"])
@roles_required("restaurant_owner", "admin")
def proof_decide(proof_id):
    proof = db.session.get(PaymentProof, proof_id) or abort(404)
    order = proof.order
    if current_user.role == "restaurant_owner" and (not current_user.restaurant or current_user.restaurant.id != order.restaurant_id):
        abort(403)
    decision = request.form.get("decision")
    if proof.status != "pending":
        flash("This proof has already been reviewed.", "info")
        return back("owner_verifications" if current_user.role == "restaurant_owner" else "admin_proofs")
    if decision == "approve":
        proof.status, order.payment_status = "approved", "paid"
        if order.payment:
            order.payment.status = "paid"
        if order.status == "placed":
            order.status = "confirmed"
        notify(order.customer_id, f"Payment confirmed for order #{order.id}",
               "Your payment was verified and the restaurant has confirmed your order.", url_for("customer_order_detail", order_id=order.id))
        notify(order.restaurant.owner_id, f"Payment approved for order #{order.id}", "The order is confirmed.",
               url_for("owner_orders"))
        flash(f"Payment approved. Order #{order.id} is now confirmed.", "success")
    elif decision == "reject":
        note = clean(request.form.get("note"), 200)
        proof.status, proof.note, order.payment_status = "rejected", note or None, "rejected"
        if order.payment:
            order.payment.status = "failed"
        notify(order.customer_id, f"Payment proof rejected for order #{order.id}",
               (note + " " if note else "") + "Please upload a clear, valid proof of payment.",
               url_for("customer_payment", order_id=order.id))
        flash("Proof rejected and the customer has been notified.", "info")
    else:
        abort(400)
    proof.reviewed_by, proof.reviewed_at = current_user.id, utcnow()
    db.session.commit()
    return back("owner_verifications" if current_user.role == "restaurant_owner" else "admin_proofs")


# --------------------------------------------------------------------------------------
# Customer
# --------------------------------------------------------------------------------------
customer_only = roles_required("customer")


def get_cart(user):
    items = [i for i in CartItem.query.filter_by(customer_id=user.id).order_by(CartItem.id).all() if i.food]
    subtotal = sum(i.food.price * i.quantity for i in items)
    return items, subtotal, (items[0].food.restaurant if items else None)


def favorite_ids(user, kind):
    return {f.target_id for f in Favorite.query.filter_by(user_id=user.id, kind=kind).all()}


@app.route("/customer/dashboard")
@customer_only
def customer_dashboard():
    recs, rec_label = recommend_for(current_user)
    picks = ai_picks(current_user)
    active = Order.query.filter(Order.customer_id == current_user.id, ~Order.status.in_(["delivered", "cancelled"])) \
        .order_by(Order.created_at.desc()).limit(3).all()
    spent = db.session.query(func.coalesce(func.sum(Order.total_amount), 0)) \
        .filter(Order.customer_id == current_user.id, Order.status == "delivered").scalar()
    stats = {"orders": Order.query.filter_by(customer_id=current_user.id).count(),
             "spent": spent, "favorites": Favorite.query.filter_by(user_id=current_user.id).count(),
             "active": len(active)}
    restaurants, ad_ids = sponsored_first(Restaurant.query.filter_by(is_approved=True).limit(40).all())
    return render_template("customer/dashboard.html", recs=recs, rec_label=rec_label, picks=picks, active=active,
                           stats=stats, restaurants=restaurants[:4], ad_ids=ad_ids,
                           fav_foods=favorite_ids(current_user, "food"))


@app.route("/customer/search")
@customer_only
def customer_search():
    q = clean(request.args.get("q"), 120)
    results = smart_search(q) if q else None
    return render_template("customer/search.html", q=q, results=results, fav_foods=favorite_ids(current_user, "food"))


@app.route("/customer/browse-menu")
@customer_only
def customer_browse_menu():
    """Show approved restaurants as the first step in browsing their food menus."""
    q = clean(request.args.get("q"), 80)
    sort = request.args.get("sort", "rating")
    query = Restaurant.query.filter_by(is_approved=True)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Restaurant.name.ilike(like), Restaurant.description.ilike(like),
                                 Restaurant.address.ilike(like)))
    if sort == "time":
        query = query.order_by(Restaurant.delivery_time.asc())
    elif sort == "name":
        query = query.order_by(Restaurant.name.asc())
    else:
        query = query.order_by(Restaurant.rating.desc())
    restaurants = query.all()
    ad_ids = live_ad_restaurant_ids()
    restaurants.sort(key=lambda r: r.id not in ad_ids)
    return render_template("customer/restaurants.html", restaurants=restaurants, ad_ids=ad_ids, q=q, sort=sort,
                           fav_restaurants=favorite_ids(current_user, "restaurant"), browse_menu=True)


@app.route("/customer/restaurants")
@customer_only
def customer_restaurants():
    q = clean(request.args.get("q"), 80)
    sort = request.args.get("sort", "rating")
    query = Restaurant.query.filter_by(is_approved=True)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Restaurant.name.ilike(like), Restaurant.description.ilike(like),
                                 Restaurant.address.ilike(like)))
    if sort == "time":
        query = query.order_by(Restaurant.delivery_time.asc())
    elif sort == "name":
        query = query.order_by(Restaurant.name.asc())
    else:
        query = query.order_by(Restaurant.rating.desc())
    restaurants = query.all()
    ad_ids = live_ad_restaurant_ids()
    restaurants.sort(key=lambda r: r.id not in ad_ids)  # stable: sponsored first, keeps chosen order
    return render_template("customer/restaurants.html", restaurants=restaurants, ad_ids=ad_ids, q=q, sort=sort,
                           fav_restaurants=favorite_ids(current_user, "restaurant"), browse_menu=False)


@app.route("/customer/restaurant/<int:restaurant_id>")
@customer_only
def customer_menu(restaurant_id):
    restaurant = db.session.get(Restaurant, restaurant_id)
    if not restaurant or not restaurant.is_approved:
        abort(404)
    q, category = clean(request.args.get("q"), 80), clean(request.args.get("category"), 50)
    min_price, max_price = to_int(request.args.get("min"), 0, 0), to_int(request.args.get("max"), 0, 0)
    query = FoodItem.query.filter_by(restaurant_id=restaurant.id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(FoodItem.name.ilike(like), FoodItem.description.ilike(like)))
    if category:
        query = query.filter(FoodItem.category == category)
    if min_price:
        query = query.filter(FoodItem.price >= min_price)
    if max_price:
        query = query.filter(FoodItem.price <= max_price)
    foods = query.order_by(FoodItem.is_available.desc(), FoodItem.category, FoodItem.name).all()
    categories = [c[0] for c in db.session.query(FoodItem.category).filter(
        FoodItem.restaurant_id == restaurant.id, FoodItem.category.isnot(None)).distinct().order_by(FoodItem.category).all()]
    reviews = Review.query.filter_by(restaurant_id=restaurant.id).order_by(Review.created_at.desc()).limit(6).all()
    return render_template("customer/menu.html", restaurant=restaurant, foods=foods, categories=categories,
                           reviews=reviews, q=q, category=category, min_price=min_price or "", max_price=max_price or "",
                           sponsored=restaurant.id in live_ad_restaurant_ids(),
                           fav_foods=favorite_ids(current_user, "food"),
                           fav_restaurants=favorite_ids(current_user, "restaurant"))


@app.route("/customer/favorite/toggle", methods=["POST"])
@customer_only
def favorite_toggle():
    kind, target = request.form.get("kind"), to_int(request.form.get("id"))
    if kind not in ("food", "restaurant"):
        return jsonify(ok=False, message="Invalid request."), 400
    exists = db.session.get(FoodItem if kind == "food" else Restaurant, target)
    if not exists:
        return jsonify(ok=False, message="That item no longer exists."), 404
    fav = Favorite.query.filter_by(user_id=current_user.id, kind=kind, target_id=target).first()
    if fav:
        db.session.delete(fav)
        active, message = False, "Removed from favorites"
    else:
        db.session.add(Favorite(user_id=current_user.id, kind=kind, target_id=target))
        active, message = True, "Added to favorites"
    db.session.commit()
    return jsonify(ok=True, active=active, message=message)


@app.route("/customer/favorites")
@customer_only
def customer_favorites():
    food_ids = favorite_ids(current_user, "food")
    rest_ids = favorite_ids(current_user, "restaurant")
    foods = FoodItem.query.filter(FoodItem.id.in_(list(food_ids) or [0])).all()
    restaurants = Restaurant.query.filter(Restaurant.id.in_(list(rest_ids) or [0]), Restaurant.is_approved.is_(True)).all()
    return render_template("customer/favorites.html", foods=foods, restaurants=restaurants, fav_foods=food_ids,
                           fav_restaurants=rest_ids, ad_ids=live_ad_restaurant_ids())


# ---- cart --------------------------------------------------------------------------------
@app.route("/customer/cart")
@customer_only
def customer_cart():
    items, subtotal, restaurant = get_cart(current_user)
    return render_template("customer/cart.html", items=items, restaurant=restaurant, totals=calc_totals(subtotal) if items else None)


@app.route("/customer/cart/add", methods=["POST"])
@customer_only
def cart_add():
    food = db.session.get(FoodItem, to_int(request.form.get("food_id")))
    qty = to_int(request.form.get("quantity"), 1, 1, 20)
    if not food or not food.restaurant.is_approved:
        return jsonify(ok=False, message="This dish is no longer available."), 404
    if not food.is_available or not food.restaurant.is_open:
        return jsonify(ok=False, message="This dish or restaurant is not taking orders right now."), 409
    items, _, current_restaurant = get_cart(current_user)
    if current_restaurant and current_restaurant.id != food.restaurant_id:
        if request.form.get("replace") != "1":
            return jsonify(ok=False, code="other_restaurant",
                           message=f"Your cart has items from {current_restaurant.name}. Start a new cart with {food.restaurant.name}?"), 409
        CartItem.query.filter_by(customer_id=current_user.id).delete()
    line = CartItem.query.filter_by(customer_id=current_user.id, food_id=food.id).first()
    if line:
        line.quantity = min(20, line.quantity + qty)
    else:
        db.session.add(CartItem(customer_id=current_user.id, food_id=food.id, quantity=qty))
    db.session.commit()
    count = db.session.query(func.coalesce(func.sum(CartItem.quantity), 0)).filter(CartItem.customer_id == current_user.id).scalar()
    return jsonify(ok=True, message=f"{food.name} added to cart", count=int(count))


@app.route("/customer/cart/update", methods=["POST"])
@customer_only
def cart_update():
    line = CartItem.query.filter_by(id=to_int(request.form.get("id")), customer_id=current_user.id).first_or_404()
    action = request.form.get("action")
    if action == "inc":
        line.quantity = min(20, line.quantity + 1)
    elif action == "dec":
        line.quantity -= 1
        if line.quantity < 1:
            db.session.delete(line)
    elif action == "remove":
        db.session.delete(line)
    db.session.commit()
    return redirect(url_for("customer_cart"))


@app.route("/customer/cart/clear", methods=["POST"])
@customer_only
def cart_clear():
    CartItem.query.filter_by(customer_id=current_user.id).delete()
    db.session.commit()
    flash("Your cart is empty.", "info")
    return redirect(url_for("customer_cart"))


# ---- checkout & payment ------------------------------------------------------------------
@app.route("/customer/checkout", methods=["GET", "POST"])
@customer_only
def customer_checkout():
    items, subtotal, restaurant = get_cart(current_user)
    if not items:
        flash("Your cart is empty. Add something tasty first.", "info")
        return redirect(url_for("customer_restaurants"))
    totals = calc_totals(subtotal)
    if request.method == "POST":
        address, phone = clean_block(request.form.get("delivery_address"), 500), clean(request.form.get("phone"), 20)
        method, note = request.form.get("payment_method"), clean(request.form.get("note"), 250)
        lat, lng = to_float(request.form.get("lat")), to_float(request.form.get("lng"))
        if lat is not None and lng is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
            lat = lng = None
        error = None
        if len(address) < 8:
            error = "Please enter a full delivery address."
        elif not valid_phone(phone):
            error = "Please enter a valid phone number."
        elif method not in ("cod", "online"):
            error = "Choose a payment method."
        elif not restaurant.is_approved or not restaurant.is_open:
            error = f"{restaurant.name} is not taking orders right now."
        elif any(not i.food.is_available for i in items):
            error = "Some dishes in your cart are no longer available. Remove them and try again."
        elif method == "online" and not (restaurant.bank_name and restaurant.account_number):
            error = "This restaurant has not added bank details yet. Please pay with cash on delivery."
        if error:
            flash(error, "error")
        else:
            order = Order(customer_id=current_user.id, restaurant_id=restaurant.id, subtotal=subtotal,
                          total_amount=totals["total"], service_charge=totals["service_charge"],
                          commission=totals["commission"], status="placed", payment_method=method,
                          payment_status="pending", delivery_address=address, customer_phone=phone,
                          lat=lat, lng=lng, note=note or None)
            db.session.add(order)
            db.session.flush()
            for line in items:
                db.session.add(OrderItem(order_id=order.id, food_id=line.food_id, food_name=line.food.name,
                                         quantity=line.quantity, price=line.food.price))
            db.session.add(Payment(order_id=order.id, method="Online payment" if method == "online" else "Cash on delivery",
                                   amount=order.total_amount, status="pending"))
            CartItem.query.filter_by(customer_id=current_user.id).delete()
            current_user.phone = current_user.phone or phone
            run_fraud_checks(order)
            notify(restaurant.owner_id, f"New order #{order.id}", f"{len(items)} item(s) - \u20a6{subtotal:,}", url_for("owner_orders"))
            notify(current_user.id, f"Order #{order.id} placed", f"{restaurant.name} will confirm it shortly.",
                   url_for("customer_order_detail", order_id=order.id))
            db.session.commit()
            if method == "online":
                flash("Order placed. Complete your payment and upload the proof to confirm it.", "info")
                return redirect(url_for("customer_payment", order_id=order.id))
            flash("Order placed! Pay cash when it arrives.", "success")
            return redirect(url_for("customer_order_detail", order_id=order.id))
    return render_template("customer/checkout.html", items=items, restaurant=restaurant, totals=totals)


def own_order(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    if order.customer_id != current_user.id:
        abort(404)
    return order


@app.route("/customer/payment/<int:order_id>")
@customer_only
def customer_payment(order_id):
    order = own_order(order_id)
    if order.payment_method != "online":
        return redirect(url_for("customer_order_detail", order_id=order.id))
    ref = f"SB{order.id}-{int(time.time())}"
    return render_template("customer/payment.html", order=order, paystack_ref=ref,
                           can_upload=order.status == "placed" and order.payment_status in ("pending", "rejected"))


@app.route("/customer/payment/<int:order_id>/proof", methods=["POST"])
@customer_only
def customer_upload_proof(order_id):
    order = own_order(order_id)
    if order.payment_method != "online" or order.status != "placed" or order.payment_status not in ("pending", "rejected"):
        flash("This order cannot accept a payment proof right now.", "error")
        return redirect(url_for("customer_payment", order_id=order.id))
    path, error = upload_or_flash("proof", "uploads/proofs", 1600)
    if error or not path:
        flash(error or "Please choose the image of your payment receipt (JPG or PNG).", "error")
        return redirect(url_for("customer_payment", order_id=order.id))
    db.session.add(PaymentProof(order_id=order.id, customer_id=current_user.id, image_path=path, status="pending"))
    order.payment_status = "awaiting_verification"
    if order.payment:
        order.payment.status = "verifying"
    notify(order.restaurant.owner_id, f"Payment proof for order #{order.id}", "Review it in Payment Verifications.",
           url_for("owner_verifications"))
    notify_admins(f"Payment proof uploaded for order #{order.id}", "", url_for("admin_proofs"))
    db.session.commit()
    flash("Payment proof uploaded. It is now under verification.", "success")
    return redirect(url_for("customer_payment", order_id=order.id))


@app.route("/customer/payment/<int:order_id>/reference", methods=["POST"])
@customer_only
def customer_paystack_reference(order_id):
    order = own_order(order_id)
    ref = clean(request.form.get("reference"), 100)
    if not re.fullmatch(r"[A-Za-z0-9._=-]{6,100}", ref):
        return jsonify(ok=False, message="Invalid payment reference."), 400
    order.paystack_ref = ref
    if order.payment:
        order.payment.reference = ref
    db.session.commit()
    return jsonify(ok=True, message="Payment reference saved. Now upload your proof of payment.")


# ---- orders ------------------------------------------------------------------------------
@app.route("/customer/orders")
@customer_only
def customer_orders():
    status = request.args.get("status", "")
    query = Order.query.filter_by(customer_id=current_user.id)
    if status in STATUS_LABEL:
        query = query.filter_by(status=status)
    pagination = query.order_by(Order.created_at.desc()).paginate(page=to_int(request.args.get("page"), 1, 1), per_page=10, error_out=False)
    return render_template("customer/orders.html", pagination=pagination, status=status)


@app.route("/customer/orders/<int:order_id>")
@customer_only
def customer_order_detail(order_id):
    order = own_order(order_id)
    review = Review.query.filter_by(order_id=order.id).first()
    return render_template("customer/order_detail.html", order=order, review=review)


@app.route("/customer/orders/<int:order_id>/cancel", methods=["POST"])
@customer_only
def customer_cancel_order(order_id):
    order = own_order(order_id)
    if order.status != "placed":
        flash("This order is already being prepared and can no longer be cancelled.", "error")
    else:
        order.status = "cancelled"
        RiderLocation.query.filter_by(order_id=order.id).delete()
        if order.payment:
            order.payment.status = "cancelled"
        notify(order.restaurant.owner_id, f"Order #{order.id} cancelled", "The customer cancelled this order.", url_for("owner_orders"))
        db.session.commit()
        flash("Order cancelled.", "info")
    return redirect(url_for("customer_order_detail", order_id=order.id))


@app.route("/customer/orders/<int:order_id>/review", methods=["POST"])
@customer_only
def customer_review(order_id):
    order = own_order(order_id)
    rating, comment = to_int(request.form.get("rating"), 0, 0, 5), clean_block(request.form.get("comment"), 800)
    if order.status != "delivered":
        flash("You can review an order after it is delivered.", "error")
    elif Review.query.filter_by(order_id=order.id).first():
        flash("You have already reviewed this order.", "info")
    elif rating < 1:
        flash("Please choose a star rating.", "error")
    else:
        db.session.add(Review(customer_id=current_user.id, restaurant_id=order.restaurant_id, order_id=order.id,
                              rating=rating, comment=comment or None))
        db.session.flush()
        avg, count = db.session.query(func.avg(Review.rating), func.count(Review.id)) \
            .filter(Review.restaurant_id == order.restaurant_id).one()
        order.restaurant.rating, order.restaurant.rating_count = round(float(avg or 0), 1), int(count or 0)
        notify(order.restaurant.owner_id, f"New {rating}-star review", comment[:120] if comment else "", url_for("owner_dashboard"))
        db.session.commit()
        flash("Thanks for your review!", "success")
    return redirect(url_for("customer_order_detail", order_id=order.id))


@app.route("/customer/tracking")
@customer_only
def customer_tracking():
    active = Order.query.filter(Order.customer_id == current_user.id, ~Order.status.in_(["delivered", "cancelled"])) \
        .order_by(Order.created_at.desc()).all()
    recent = Order.query.filter(Order.customer_id == current_user.id, Order.status.in_(["delivered", "cancelled"])) \
        .order_by(Order.updated_at.desc()).limit(3).all()
    return render_template("customer/tracking.html", active=active, recent=recent)


@app.route("/customer/api/order/<int:order_id>/status")
@customer_only
def customer_order_status(order_id):
    order = own_order(order_id)
    return jsonify(status=order.status, label=STATUS_LABEL[order.status], stage=order.rider_stage or "",
                   payment=order.payment_status)


@app.route("/customer/api/order/<int:order_id>/location")
@customer_only
def customer_order_location(order_id):
    """Expose only the assigned rider's latest location to the order's customer."""
    order = own_order(order_id)
    if not order.rider_id or order.status in ("delivered", "cancelled"):
        return jsonify(available=False, message="Live tracking is not available for this order.")
    location = RiderLocation.query.filter_by(rider_id=order.rider_id, order_id=order.id).first()
    if not location:
        return jsonify(available=False, message="Waiting for your rider to share their location.")
    age = (utcnow() - location.updated_at).total_seconds()
    return jsonify(available=age <= 60, latitude=location.latitude, longitude=location.longitude,
                   accuracy=location.accuracy, updated_at=location.updated_at.isoformat() + "Z",
                   stale=age > 60, message="Rider location is updating." if age <= 60 else "Last location update is more than one minute old.")


# --------------------------------------------------------------------------------------
# Restaurant owner
# --------------------------------------------------------------------------------------
owner_only = roles_required("restaurant_owner")


def restaurant_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.role != "restaurant_owner":
            abort(403)
        if not current_user.restaurant:
            flash("Create your restaurant profile first.", "info")
            return redirect(url_for("owner_profile"))
        return fn(*args, **kwargs)
    return wrapper


def delivered_orders(restaurant_id):
    return Order.query.filter_by(restaurant_id=restaurant_id, status="delivered")


@app.route("/restaurant/dashboard")
@restaurant_required
def owner_dashboard():
    r = current_user.restaurant
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = Order.query.filter(Order.restaurant_id == r.id, Order.created_at >= today_start, Order.status != "cancelled")
    stats = {"today_orders": today_orders.count(),
             "today_sales": db.session.query(func.coalesce(func.sum(Order.subtotal), 0)).filter(
                 Order.restaurant_id == r.id, Order.created_at >= today_start, Order.status != "cancelled").scalar(),
             "pending": Order.query.filter_by(restaurant_id=r.id, status="placed").count(),
             "verifications": PaymentProof.query.join(Order, Order.id == PaymentProof.order_id)
             .filter(Order.restaurant_id == r.id, PaymentProof.status == "pending").count(),
             "foods": FoodItem.query.filter_by(restaurant_id=r.id).count(),
             "rating": r.rating or 0}
    recent = Order.query.filter_by(restaurant_id=r.id).order_by(Order.created_at.desc()).limit(6).all()
    forecasts, _ = demand_forecast(r.id)
    return render_template("restaurant/dashboard.html", r=r, stats=stats, recent=recent, forecasts=forecasts[:3])


# ---- foods -------------------------------------------------------------------------------
@app.route("/restaurant/foods")
@restaurant_required
def owner_foods():
    q = clean(request.args.get("q"), 80)
    query = FoodItem.query.filter_by(restaurant_id=current_user.restaurant.id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(FoodItem.name.ilike(like), FoodItem.category.ilike(like)))
    return render_template("restaurant/foods.html", foods=query.order_by(FoodItem.category, FoodItem.name).all(), q=q)


def _save_food(food):
    name, desc = clean(request.form.get("name"), 100), clean_block(request.form.get("description"), 600)
    price, category = to_int(request.form.get("price"), 0, 0, 10_000_000), clean(request.form.get("category"), 50)
    if len(name) < 2:
        return "Please enter the dish name."
    if price < 1:
        return "Enter a price greater than zero."
    path, error = upload_or_flash("image", "uploads", 1000)
    if error:
        return error
    if path:
        delete_image(food.image)
        food.image = path
    food.name, food.description, food.price, food.category = name, desc, price, category or None
    food.is_available = bool(request.form.get("is_available"))
    return None


@app.route("/restaurant/foods/new", methods=["GET", "POST"])
@restaurant_required
def owner_food_new():
    food = FoodItem(restaurant_id=current_user.restaurant.id, is_available=True)
    if request.method == "POST":
        error = _save_food(food)
        if error:
            flash(error, "error")
        else:
            db.session.add(food)
            db.session.commit()
            flash(f"{food.name} added to your menu.", "success")
            return redirect(url_for("owner_foods"))
    return render_template("restaurant/food_form.html", food=food, categories=Category.query.order_by(Category.name).all(), is_new=True)


@app.route("/restaurant/foods/<int:food_id>/edit", methods=["GET", "POST"])
@restaurant_required
def owner_food_edit(food_id):
    food = FoodItem.query.filter_by(id=food_id, restaurant_id=current_user.restaurant.id).first_or_404()
    if request.method == "POST":
        error = _save_food(food)
        if error:
            flash(error, "error")
            db.session.rollback()
        else:
            db.session.commit()
            flash("Dish updated.", "success")
            return redirect(url_for("owner_foods"))
    return render_template("restaurant/food_form.html", food=food, categories=Category.query.order_by(Category.name).all(), is_new=False)


@app.route("/restaurant/foods/<int:food_id>/delete", methods=["POST"])
@restaurant_required
def owner_food_delete(food_id):
    food = FoodItem.query.filter_by(id=food_id, restaurant_id=current_user.restaurant.id).first_or_404()
    Favorite.query.filter_by(kind="food", target_id=food.id).delete()
    delete_image(food.image)
    db.session.delete(food)
    db.session.commit()
    flash("Dish deleted.", "info")
    return redirect(url_for("owner_foods"))


@app.route("/restaurant/foods/<int:food_id>/toggle", methods=["POST"])
@restaurant_required
def owner_food_toggle(food_id):
    food = FoodItem.query.filter_by(id=food_id, restaurant_id=current_user.restaurant.id).first_or_404()
    food.is_available = not food.is_available
    db.session.commit()
    flash(f"{food.name} is now {'available' if food.is_available else 'unavailable'}.", "success")
    return back("owner_foods")


# ---- orders ------------------------------------------------------------------------------
@app.route("/restaurant/orders")
@restaurant_required
def owner_orders():
    r = current_user.restaurant
    view = request.args.get("view", "active")
    query = Order.query.filter_by(restaurant_id=r.id)
    if view == "new":
        query = query.filter_by(status="placed")
    elif view == "done":
        query = query.filter(Order.status.in_(["delivered", "cancelled"]))
    elif view != "all":
        view = "active"
        query = query.filter(~Order.status.in_(["delivered", "cancelled"]))
    pagination = query.order_by(Order.created_at.desc()).paginate(page=to_int(request.args.get("page"), 1, 1), per_page=15, error_out=False)
    return render_template("restaurant/orders.html", pagination=pagination, view=view)


@app.route("/restaurant/orders/<int:order_id>/action", methods=["POST"])
@restaurant_required
def owner_order_action(order_id):
    order = Order.query.filter_by(id=order_id, restaurant_id=current_user.restaurant.id).first_or_404()
    action = request.form.get("action")
    link = url_for("customer_order_detail", order_id=order.id)
    if action == "accept":
        if order.status != "placed":
            flash("This order was already handled.", "info")
        elif order.payment_method == "online" and order.payment_status != "paid":
            flash("Verify the customer's payment proof before accepting this order.", "error")
        else:
            order.status = "confirmed"
            notify(order.customer_id, f"Order #{order.id} confirmed", f"{order.restaurant.name} accepted your order.", link)
            flash(f"Order #{order.id} accepted.", "success")
    elif action == "reject":
        if order.status not in ("placed", "confirmed") or order.rider_id:
            flash("This order can no longer be rejected.", "error")
        else:
            order.status = "cancelled"
            if order.payment:
                order.payment.status = "cancelled"
            msg = f"{order.restaurant.name} could not accept your order."
            if order.payment_status == "paid":
                msg += " Contact the restaurant about your refund."
            notify(order.customer_id, f"Order #{order.id} rejected", msg, link)
            flash(f"Order #{order.id} rejected.", "info")
    elif action == "preparing":
        if order.status != "confirmed":
            flash("Only confirmed orders can move to preparing.", "error")
        else:
            order.status = "preparing"
            notify(order.customer_id, f"Order #{order.id} is being prepared", "The kitchen has started cooking.", link)
            flash(f"Order #{order.id} is now being prepared.", "success")
    else:
        abort(400)
    db.session.commit()
    return back("owner_orders")


@app.route("/restaurant/verifications")
@restaurant_required
def owner_verifications():
    r = current_user.restaurant
    proofs = PaymentProof.query.join(Order, Order.id == PaymentProof.order_id).filter(Order.restaurant_id == r.id) \
        .order_by((PaymentProof.status == "pending").desc(), PaymentProof.uploaded_at.desc()).limit(100).all()
    return render_template("restaurant/verifications.html", proofs=proofs)


# ---- analytics & earnings ----------------------------------------------------------------
@app.route("/restaurant/analytics")
@restaurant_required
def owner_analytics():
    r = current_user.restaurant
    days = last_days(30)
    since = datetime.combine(days[0], datetime.min.time())
    sales = db.session.query(func.date(Order.created_at), func.sum(Order.subtotal)) \
        .filter(Order.restaurant_id == r.id, Order.status != "cancelled", Order.created_at >= since) \
        .group_by(func.date(Order.created_at)).all()
    counts = db.session.query(func.date(Order.created_at), func.count(Order.id)) \
        .filter(Order.restaurant_id == r.id, Order.status != "cancelled", Order.created_at >= since) \
        .group_by(func.date(Order.created_at)).all()
    labels = [d.strftime("%d %b") for d in days]
    sales_chart = {"type": "line", "labels": labels, "money": True,
                   "datasets": [{"label": "Sales", "data": series_by_day(sales, days), "color": "#FF8C42"}]}
    orders_chart = {"type": "bar", "labels": labels,
                    "datasets": [{"label": "Orders", "data": series_by_day(counts, days), "color": "#4CAF7D"}]}
    top = db.session.query(OrderItem.food_name, func.sum(OrderItem.quantity)).join(Order, Order.id == OrderItem.order_id) \
        .filter(Order.restaurant_id == r.id, Order.status != "cancelled") \
        .group_by(OrderItem.food_name).order_by(func.sum(OrderItem.quantity).desc()).limit(8).all()
    top_chart = {"type": "bar", "horizontal": True, "labels": [t[0] for t in top],
                 "datasets": [{"label": "Portions sold", "data": [int(t[1]) for t in top], "color": "#FF8C42"}]}
    status_rows = db.session.query(Order.status, func.count(Order.id)).filter(Order.restaurant_id == r.id).group_by(Order.status).all()
    status_chart = {"type": "doughnut", "labels": [STATUS_LABEL[s] for s, _ in status_rows],
                    "datasets": [{"label": "Orders", "data": [c for _, c in status_rows]}]}
    forecasts, forecast_chart = demand_forecast(r.id)
    return render_template("restaurant/analytics.html", sales_chart=sales_chart, orders_chart=orders_chart,
                           top_chart=top_chart, status_chart=status_chart, forecasts=forecasts,
                           forecast_chart=forecast_chart, has_data=bool(status_rows))


@app.route("/restaurant/earnings")
@restaurant_required
def owner_earnings():
    r = current_user.restaurant
    done = delivered_orders(r.id)
    agg = db.session.query(func.coalesce(func.sum(Order.total_amount), 0), func.coalesce(func.sum(Order.commission), 0),
                           func.coalesce(func.sum(Order.service_charge), 0), func.coalesce(func.sum(Order.subtotal), 0),
                           func.count(Order.id)).filter(Order.restaurant_id == r.id, Order.status == "delivered").one()
    month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_net = db.session.query(func.coalesce(func.sum(Order.subtotal), 0)).filter(
        Order.restaurant_id == r.id, Order.status == "delivered", Order.created_at >= month_start).scalar()
    payroll = db.session.query(func.coalesce(func.sum(StaffMember.monthly_salary), 0)).filter(StaffMember.restaurant_id == r.id).scalar()
    days = last_days(30)
    since = datetime.combine(days[0], datetime.min.time())
    net_rows = db.session.query(func.date(Order.created_at), func.sum(Order.subtotal)) \
        .filter(Order.restaurant_id == r.id, Order.status == "delivered", Order.created_at >= since) \
        .group_by(func.date(Order.created_at)).all()
    chart = {"type": "line", "labels": [d.strftime("%d %b") for d in days], "money": True,
             "datasets": [{"label": "Net earnings", "data": series_by_day(net_rows, days), "color": "#4CAF7D"}]}
    totals = {"gross": agg[0], "commission": agg[1], "service": agg[2], "net": agg[3], "orders": agg[4],
              "month_net": month_net, "payroll": payroll, "month_profit": month_net - payroll}
    return render_template("restaurant/earnings.html", totals=totals, earnings_chart=chart,
                           recent=done.order_by(Order.created_at.desc()).limit(15).all())


# ---- staff -------------------------------------------------------------------------------
@app.route("/restaurant/staff", methods=["GET", "POST"])
@restaurant_required
def owner_staff():
    r = current_user.restaurant
    if request.method == "POST":
        f = {k: clean(request.form.get(k), 100) for k in ("name", "email", "phone", "staff_role")}
        f["email"] = f["email"].lower()
        password, salary = request.form.get("password", ""), to_int(request.form.get("salary"), -1, -1, 100_000_000)
        error = None
        if len(f["name"]) < 2:
            error = "Enter the staff member's name."
        elif not valid_email(f["email"]):
            error = "Enter a valid email address."
        elif not valid_phone(f["phone"]):
            error = "Enter a valid phone number."
        elif f["staff_role"] not in ("cook", "packager"):
            error = "Choose cook or packager."
        elif salary < 0:
            error = "Enter the monthly salary."
        elif password_problem(password):
            error = password_problem(password)
        elif User.query.filter_by(email=f["email"]).first():
            error = "A user with this email already exists."
        if error:
            flash(error, "error")
        else:
            user = User(name=f["name"], email=f["email"], phone=f["phone"], address=r.address, role="staff",
                        password_hash=generate_password_hash(password), must_change_password=True)
            db.session.add(user)
            db.session.flush()
            db.session.add(StaffMember(user_id=user.id, restaurant_id=r.id, staff_role=f["staff_role"], monthly_salary=salary))
            db.session.commit()
            flash(f"{f['name']} added. They must set a new password at first login.", "success")
            return redirect(url_for("owner_staff"))
    members = StaffMember.query.filter_by(restaurant_id=r.id).order_by(StaffMember.hired_at.desc()).all()
    return render_template("restaurant/staff.html", members=members)


@app.route("/restaurant/staff/<int:member_id>/update", methods=["POST"])
@restaurant_required
def owner_staff_update(member_id):
    member = StaffMember.query.filter_by(id=member_id, restaurant_id=current_user.restaurant.id).first_or_404()
    role = request.form.get("staff_role")
    salary = to_int(request.form.get("salary"), -1, -1, 100_000_000)
    if role not in ("cook", "packager") or salary < 0:
        flash("Enter a valid role and salary.", "error")
    else:
        member.staff_role, member.monthly_salary = role, salary
        db.session.commit()
        flash("Staff details updated.", "success")
    return redirect(url_for("owner_staff"))


@app.route("/restaurant/staff/<int:member_id>/delete", methods=["POST"])
@restaurant_required
def owner_staff_delete(member_id):
    member = StaffMember.query.filter_by(id=member_id, restaurant_id=current_user.restaurant.id).first_or_404()
    user = member.user
    delete_image(user.profile_image)
    db.session.delete(member)
    db.session.flush()
    Notification.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash("Staff member removed.", "info")
    return redirect(url_for("owner_staff"))


# ---- sponsored ads -----------------------------------------------------------------------
@app.route("/restaurant/ads", methods=["GET", "POST"])
@restaurant_required
def owner_ads():
    r = current_user.restaurant
    price = get_int("ad_price_per_week")
    if request.method == "POST":
        weeks = to_int(request.form.get("weeks"), 0, 0, 26)
        if not r.is_approved:
            flash("Your restaurant must be approved before you can advertise.", "error")
        elif weeks < 1:
            flash("Choose how many weeks to advertise (1 to 26).", "error")
        elif price < 1:
            flash("Advertising is not available yet. Please check back soon.", "error")
        else:
            path, error = upload_or_flash("proof", "uploads/proofs", 1600)
            if error or not path:
                flash(error or "Upload the proof of your ad payment (JPG or PNG).", "error")
            else:
                db.session.add(Ad(restaurant_id=r.id, weeks=weeks, amount=weeks * price, proof_image=path, status="pending"))
                notify_admins("New sponsored ad request", f"{r.name} - {weeks} week(s), \u20a6{weeks * price:,}", url_for("admin_ads"))
                db.session.commit()
                flash("Ad request sent. It goes live once the payment is verified.", "success")
                return redirect(url_for("owner_ads"))
    ads = Ad.query.filter_by(restaurant_id=r.id).order_by(Ad.created_at.desc()).all()
    bank = {k: get_setting(f"admin_{k}") for k in ("bank_name", "account_name", "account_number")}
    return render_template("restaurant/ads.html", ads=ads, price=price, bank=bank)


# ---- restaurant profile ------------------------------------------------------------------
@app.route("/restaurant/profile")
@owner_only
def owner_profile():
    return render_template("restaurant/profile.html", r=current_user.restaurant)


@app.route("/restaurant/profile/save", methods=["POST"])
@owner_only
def owner_profile_save():
    r = current_user.restaurant
    is_new = r is None
    f = {k: clean(request.form.get(k), 100) for k in ("name", "phone", "bank_name", "account_name", "account_number")}
    description, address = clean_block(request.form.get("description"), 800), clean_block(request.form.get("address"), 400)
    delivery_time = to_int(request.form.get("delivery_time"), 35, 5, 240)
    lat, lng = to_float(request.form.get("lat")), to_float(request.form.get("lng"))
    if lat is not None and lng is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
        lat = lng = None
    error = None
    if len(f["name"]) < 2:
        error = "Enter the restaurant name."
    elif len(address) < 5:
        error = "Enter the restaurant address."
    elif not valid_phone(f["phone"]):
        error = "Enter a valid restaurant phone number."
    elif f["account_number"] and not re.fullmatch(r"[0-9]{6,20}", f["account_number"]):
        error = "The account number should contain digits only."
    path, img_error = (None, None) if error else upload_or_flash("image", "uploads", 1200)
    error = error or img_error
    if error:
        flash(error, "error")
        return redirect(url_for("owner_profile"))
    if is_new:
        r = Restaurant(owner_id=current_user.id, status="pending", is_approved=False)
        db.session.add(r)
    if path:
        delete_image(r.image)
        r.image = path
    r.name, r.description, r.address, r.phone = f["name"], description, address, f["phone"]
    r.bank_name, r.account_name, r.account_number = f["bank_name"] or None, f["account_name"] or None, f["account_number"] or None
    r.delivery_time, r.lat, r.lng = delivery_time, lat, lng
    if is_new:
        notify_admins("New restaurant awaiting approval", f"{r.name} has been created.", url_for("admin_restaurants", status="pending"))
    db.session.commit()
    flash("Restaurant profile created. We will review it shortly." if is_new else "Restaurant profile saved.", "success")
    return redirect(url_for("owner_profile"))


@app.route("/restaurant/profile/toggle-open", methods=["POST"])
@restaurant_required
def owner_toggle_open():
    r = current_user.restaurant
    r.is_open = not r.is_open
    db.session.commit()
    flash("Your restaurant is now open for orders." if r.is_open else "Your restaurant is now closed to new orders.", "success")
    return redirect(url_for("owner_profile"))


@app.route("/restaurant/profile/delete", methods=["POST"])
@restaurant_required
def owner_profile_delete():
    r = current_user.restaurant
    if not check_password_hash(current_user.password_hash, request.form.get("password", "")):
        flash("Password incorrect. Your restaurant was not deleted.", "error")
    elif Order.query.filter_by(restaurant_id=r.id).count():
        flash("A restaurant with order history cannot be deleted. Close it instead so it stops taking orders.", "error")
    else:
        for member in list(r.staff):
            staff_user = member.user
            db.session.delete(member)
            db.session.flush()
            Notification.query.filter_by(user_id=staff_user.id).delete()
            db.session.delete(staff_user)
        for food in r.foods:
            delete_image(food.image)
        Favorite.query.filter_by(kind="restaurant", target_id=r.id).delete()
        delete_image(r.image)
        db.session.delete(r)
        db.session.commit()
        flash("Restaurant deleted. You can create a new profile any time.", "info")
    return redirect(url_for("owner_profile"))


# --------------------------------------------------------------------------------------
# Restaurant staff (cook / packager): kitchen queue and own salary only
# --------------------------------------------------------------------------------------
def staff_member_or_403():
    member = current_user.staff_profile
    if not member:
        abort(403)
    return member


@app.route("/staff/dashboard")
@roles_required("staff")
def staff_dashboard():
    member = staff_member_or_403()
    queue = Order.query.filter(Order.restaurant_id == member.restaurant_id, Order.status.in_(["confirmed", "preparing"])) \
        .order_by(Order.created_at.asc()).all()
    return render_template("staff/dashboard.html", member=member, queue=queue)


@app.route("/staff/orders/<int:order_id>/action", methods=["POST"])
@roles_required("staff")
def staff_order_action(order_id):
    member = staff_member_or_403()
    order = Order.query.filter_by(id=order_id, restaurant_id=member.restaurant_id).first_or_404()
    action = request.form.get("action")
    if action == "preparing" and member.staff_role == "cook" and order.status == "confirmed":
        order.status = "preparing"
        notify(order.customer_id, f"Order #{order.id} is being prepared", "The kitchen has started cooking.",
               url_for("customer_order_detail", order_id=order.id))
        flash(f"Order #{order.id} marked as preparing.", "success")
    elif action == "packed" and member.staff_role == "packager" and order.status == "preparing" and not order.is_packed:
        order.is_packed = True
        notify(member.restaurant.owner_id, f"Order #{order.id} is packed", "Ready for rider pickup.", url_for("owner_orders"))
        flash(f"Order #{order.id} marked as packed and ready for pickup.", "success")
    else:
        flash("That action is not available for your role or this order's stage.", "error")
    db.session.commit()
    return redirect(url_for("staff_dashboard"))


@app.route("/staff/salary")
@roles_required("staff")
def staff_salary():
    return render_template("staff/salary.html", member=staff_member_or_403())


# --------------------------------------------------------------------------------------
# Delivery rider
# --------------------------------------------------------------------------------------
rider_only = roles_required("rider")
MAX_ACTIVE_DELIVERIES = 3


def rider_active_orders():
    return Order.query.filter(Order.rider_id == current_user.id, ~Order.status.in_(["delivered", "cancelled"])) \
        .order_by(Order.created_at.asc()).all()


@app.route("/rider/dashboard")
@rider_only
def rider_dashboard():
    """Rider home with delivery workload, daily earnings and quick actions."""
    active = rider_active_orders()
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    available_count = Order.query.join(Restaurant, Restaurant.id == Order.restaurant_id) \
        .filter(Order.rider_id.is_(None), Order.status.in_(["confirmed", "preparing"]),
                Restaurant.is_approved.is_(True)).count()
    completed_today = Order.query.filter(Order.rider_id == current_user.id, Order.status == "delivered",
                                         Order.delivered_at >= today_start).count()
    earned_today = db.session.query(func.coalesce(func.sum(Order.rider_fee), 0)) \
        .filter(Order.rider_id == current_user.id, Order.status == "delivered",
                Order.delivered_at >= today_start).scalar() or 0
    recent = Order.query.filter(Order.rider_id == current_user.id) \
        .order_by(Order.updated_at.desc()).limit(5).all()
    return render_template("rider/dashboard.html", active=active, available_count=available_count,
                           completed_today=completed_today, earned_today=earned_today, recent=recent,
                           max_active=MAX_ACTIVE_DELIVERIES)


@app.route("/rider/available")
@rider_only
def rider_available():
    orders = Order.query.join(Restaurant, Restaurant.id == Order.restaurant_id) \
        .filter(Order.rider_id.is_(None), Order.status.in_(["confirmed", "preparing"]), Restaurant.is_approved.is_(True)) \
        .order_by(Order.created_at.asc()).limit(50).all()
    return render_template("rider/available.html", orders=orders, fee=get_int("rider_fee"),
                           active_count=len(rider_active_orders()), max_active=MAX_ACTIVE_DELIVERIES)


@app.route("/rider/orders/<int:order_id>/accept", methods=["POST"])
@rider_only
def rider_accept(order_id):
    if len(rider_active_orders()) >= MAX_ACTIVE_DELIVERIES:
        flash(f"You can carry up to {MAX_ACTIVE_DELIVERIES} deliveries at a time. Finish one first.", "error")
        return redirect(url_for("rider_available"))
    updated = Order.query.filter(Order.id == order_id, Order.rider_id.is_(None), Order.status.in_(["confirmed", "preparing"])) \
        .update({"rider_id": current_user.id, "rider_stage": "assigned", "rider_fee": get_int("rider_fee")},
                synchronize_session=False)
    if not updated:
        db.session.rollback()
        flash("Another rider already took this order.", "info")
        return redirect(url_for("rider_available"))
    order = db.session.get(Order, order_id)
    notify(order.customer_id, f"A rider accepted order #{order.id}", f"{current_user.name} will pick it up soon.",
           url_for("customer_order_detail", order_id=order.id))
    notify(order.restaurant.owner_id, f"Rider assigned to order #{order.id}", f"{current_user.name} is on the way to pick up.",
           url_for("owner_orders"))
    db.session.commit()
    flash(f"Order #{order.id} accepted. Head to {order.restaurant.name} for pickup.", "success")
    return redirect(url_for("rider_deliveries"))


@app.route("/rider/api/location", methods=["POST"])
@rider_only
def rider_update_location():
    payload = request.get_json(silent=True) or {}
    try:
        order_id = int(payload.get("order_id"))
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
        accuracy = float(payload.get("accuracy")) if payload.get("accuracy") is not None else None
    except (TypeError, ValueError):
        return jsonify(ok=False, message="A valid order and GPS coordinates are required."), 400
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify(ok=False, message="GPS coordinates are outside the valid range."), 400
    order = Order.query.filter_by(id=order_id, rider_id=current_user.id).first()
    if not order or order.status in ("delivered", "cancelled"):
        return jsonify(ok=False, message="This delivery is not assigned to your account or is no longer active."), 403
    location = RiderLocation.query.filter_by(rider_id=current_user.id, order_id=order.id).first()
    if not location:
        location = RiderLocation(rider_id=current_user.id, order_id=order.id)
        db.session.add(location)
    location.latitude, location.longitude, location.accuracy = latitude, longitude, accuracy
    location.updated_at = utcnow()
    db.session.commit()
    return jsonify(ok=True, message="GPS location shared.", updated_at=location.updated_at.isoformat() + "Z")


@app.route("/rider/deliveries")
@rider_only
def rider_deliveries():
    return render_template("rider/deliveries.html", orders=rider_active_orders())


@app.route("/rider/orders/<int:order_id>/stage", methods=["POST"])
@rider_only
def rider_stage(order_id):
    order = Order.query.filter_by(id=order_id, rider_id=current_user.id).first_or_404()
    stage = request.form.get("stage")
    allowed = {"picked": ("assigned",), "on_the_way": ("picked",), "delivered": ("picked", "on_the_way")}
    if order.status in ("delivered", "cancelled") or stage not in allowed or order.rider_stage not in allowed[stage]:
        flash("That update is not available for this delivery right now.", "error")
        return redirect(url_for("rider_deliveries"))
    link = url_for("customer_order_detail", order_id=order.id)
    order.rider_stage = stage
    if stage == "picked":
        order.status = "out_for_delivery"
        notify(order.customer_id, f"Order #{order.id} picked up", "Your rider has collected your food.", link)
        flash("Marked as picked up.", "success")
    elif stage == "on_the_way":
        order.status = "out_for_delivery"
        notify(order.customer_id, f"Order #{order.id} is on the way", f"{current_user.name} is heading to you.", link)
        flash("Marked as on the way.", "success")
    else:
        order.status, order.delivered_at = "delivered", utcnow()
        # Stop sharing and remove stored precise coordinates once the delivery is complete.
        RiderLocation.query.filter_by(order_id=order.id).delete()
        order.payment_status = "paid"
        if order.payment:
            order.payment.status = "paid"
        notify(order.customer_id, f"Order #{order.id} delivered", "Enjoy your meal! Tell us how it was.", link)
        notify(order.restaurant.owner_id, f"Order #{order.id} delivered", "", url_for("owner_orders"))
        flash(f"Order #{order.id} delivered. You earned \u20a6{order.rider_fee:,}.", "success")
    db.session.commit()
    return redirect(url_for("rider_deliveries"))


@app.route("/rider/map")
@rider_only
def rider_map():
    orders = rider_active_orders()
    selected = to_int(request.args.get("order"), 0)
    if selected:
        orders = [o for o in orders if o.id == selected]
    stops = [{"id": o.id, "picked": o.rider_stage in ("picked", "on_the_way"),
              "restaurant": {"name": o.restaurant.name, "address": o.restaurant.address, "phone": o.restaurant.phone,
                             "lat": o.restaurant.lat, "lng": o.restaurant.lng},
              "customer": {"name": o.customer.name, "address": o.delivery_address, "phone": o.customer_phone,
                           "lat": o.lat, "lng": o.lng}} for o in orders]
    return render_template("rider/map.html", stops=stops, orders=orders, selected=selected)


@app.route("/rider/earnings")
@rider_only
def rider_earnings():
    base = db.session.query(func.coalesce(func.sum(Order.rider_fee), 0), func.count(Order.id)) \
        .filter(Order.rider_id == current_user.id, Order.status == "delivered")
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start, month_start = today_start - timedelta(days=today_start.weekday()), today_start.replace(day=1)
    total = base.one()
    totals = {"all": total[0], "count": total[1], "today": base.filter(Order.delivered_at >= today_start).one()[0],
              "week": base.filter(Order.delivered_at >= week_start).one()[0],
              "month": base.filter(Order.delivered_at >= month_start).one()[0]}
    days = last_days(14)
    rows = db.session.query(func.date(Order.delivered_at), func.sum(Order.rider_fee)) \
        .filter(Order.rider_id == current_user.id, Order.status == "delivered",
                Order.delivered_at >= datetime.combine(days[0], datetime.min.time())) \
        .group_by(func.date(Order.delivered_at)).all()
    chart = {"type": "bar", "labels": [d.strftime("%d %b") for d in days], "money": True,
             "datasets": [{"label": "Earnings", "data": series_by_day(rows, days), "color": "#4CAF7D"}]}
    return render_template("rider/earnings.html", totals=totals, earnings_chart=chart)


@app.route("/rider/history")
@rider_only
def rider_history():
    pagination = Order.query.filter(Order.rider_id == current_user.id, Order.status.in_(["delivered", "cancelled"])) \
        .order_by(Order.updated_at.desc()).paginate(page=to_int(request.args.get("page"), 1, 1), per_page=15, error_out=False)
    return render_template("rider/history.html", pagination=pagination)


# --------------------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------------------
admin_only = roles_required("admin")


def _page():
    return to_int(request.args.get("page"), 1, 1)


@app.route("/admin/dashboard")
@admin_only
def admin_dashboard():
    counts = {"users": User.query.count(), "customers": User.query.filter_by(role="customer").count(),
              "restaurants": Restaurant.query.count(), "pending_restaurants": Restaurant.query.filter_by(status="pending").count(),
              "riders": User.query.filter_by(role="rider").count(), "orders": Order.query.count(),
              "pending_proofs": PaymentProof.query.filter_by(status="pending").count(),
              "open_flags": FraudFlag.query.filter_by(status="open").count(),
              "pending_ads": Ad.query.filter_by(status="pending").count()}
    commission, service, gmv = db.session.query(func.coalesce(func.sum(Order.commission), 0),
                                                func.coalesce(func.sum(Order.service_charge), 0),
                                                func.coalesce(func.sum(Order.total_amount), 0)) \
        .filter(Order.status == "delivered").one()
    ad_revenue = db.session.query(func.coalesce(func.sum(Ad.amount), 0)).filter(Ad.status == "approved").scalar()
    revenue = {"commission": commission, "service": service, "ads": ad_revenue, "total": commission + service + ad_revenue,
               "gmv": gmv}
    days = last_days(30)
    since = datetime.combine(days[0], datetime.min.time())

    def per_day(column, *filters, date_col=Order.created_at):
        return series_by_day(db.session.query(func.date(date_col), func.sum(column)).filter(*filters, date_col >= since)
                             .group_by(func.date(date_col)).all(), days)

    labels = [d.strftime("%d %b") for d in days]
    revenue_chart = {"type": "bar", "stacked": True, "money": True, "labels": labels, "datasets": [
        {"label": "Commission", "data": per_day(Order.commission, Order.status == "delivered"), "color": "#FF8C42"},
        {"label": "Service charge", "data": per_day(Order.service_charge, Order.status == "delivered"), "color": "#4CAF7D"},
        {"label": "Sponsored ads", "data": per_day(Ad.amount, Ad.status == "approved", date_col=Ad.starts_at), "color": "#2D2D2D"}]}
    order_rows = db.session.query(func.date(Order.created_at), func.count(Order.id)) \
        .filter(Order.created_at >= since, Order.status != "cancelled").group_by(func.date(Order.created_at)).all()
    orders_chart = {"type": "line", "labels": labels,
                    "datasets": [{"label": "Orders", "data": series_by_day(order_rows, days), "color": "#FF8C42"}]}
    role_rows = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
    users_chart = {"type": "doughnut", "labels": [r.replace("_", " ").title() for r, _ in role_rows],
                   "datasets": [{"label": "Users", "data": [c for _, c in role_rows]}]}
    status_rows = db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    status_chart = {"type": "bar", "labels": [STATUS_LABEL[s] for s, _ in status_rows],
                    "datasets": [{"label": "Orders", "data": [c for _, c in status_rows], "color": "#4CAF7D"}]}
    return render_template("admin/dashboard.html", counts=counts, revenue=revenue, revenue_chart=revenue_chart,
                           orders_chart=orders_chart, users_chart=users_chart, status_chart=status_chart)


# ---- users -------------------------------------------------------------------------------
@app.route("/admin/users")
@admin_only
def admin_users():
    role, q = request.args.get("role", ""), clean(request.args.get("q"), 80)
    query = User.query
    if role in ("customer", "restaurant_owner", "rider", "admin", "staff"):
        query = query.filter_by(role=role)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), User.phone.ilike(like)))
    pagination = query.order_by(User.created_at.desc()).paginate(page=_page(), per_page=20, error_out=False)
    return render_template("admin/users.html", pagination=pagination, role=role, q=q)


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@admin_only
def admin_user_toggle(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "error")
    else:
        user.active = not user.active
        db.session.commit()
        flash(f"{user.name} is now {'active' if user.active else 'deactivated'}.", "success")
    return back("admin_users")


def _remove_staff_user(member):
    staff_user = member.user
    delete_image(staff_user.profile_image)
    db.session.delete(member)
    db.session.flush()
    Notification.query.filter_by(user_id=staff_user.id).delete()
    db.session.delete(staff_user)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_only
def admin_user_delete(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.role == "admin":
        flash("Admin accounts cannot be deleted here.", "error")
    elif Order.query.filter(or_(Order.customer_id == user.id, Order.rider_id == user.id)).count() or \
            (user.restaurant and Order.query.filter_by(restaurant_id=user.restaurant.id).count()):
        flash("This user has order history. Deactivate the account instead of deleting it.", "error")
    else:
        if user.restaurant:
            for member in list(user.restaurant.staff):
                _remove_staff_user(member)
            for food in user.restaurant.foods:
                delete_image(food.image)
            delete_image(user.restaurant.image)
            db.session.delete(user.restaurant)
        if user.staff_profile:
            db.session.delete(user.staff_profile)
        for model, column in ((CartItem, CartItem.customer_id), (Favorite, Favorite.user_id),
                              (Notification, Notification.user_id), (Review, Review.customer_id)):
            model.query.filter(column == user.id).delete()
        delete_image(user.profile_image)
        db.session.flush()
        db.session.delete(user)
        db.session.commit()
        flash("User deleted.", "info")
    return back("admin_users")


# ---- restaurants, riders -----------------------------------------------------------------
@app.route("/admin/restaurants")
@admin_only
def admin_restaurants():
    status = request.args.get("status", "")
    query = Restaurant.query
    if status in ("pending", "approved", "rejected"):
        query = query.filter_by(status=status)
    pagination = query.order_by(Restaurant.created_at.desc()).paginate(page=_page(), per_page=20, error_out=False)
    return render_template("admin/restaurants.html", pagination=pagination, status=status, ad_ids=live_ad_restaurant_ids())


@app.route("/admin/restaurants/<int:restaurant_id>/<action>", methods=["POST"])
@admin_only
def admin_restaurant_action(restaurant_id, action):
    r = db.session.get(Restaurant, restaurant_id) or abort(404)
    if action == "approve":
        r.is_approved, r.status = True, "approved"
        notify(r.owner_id, "Your restaurant is approved", f"{r.name} is now visible to customers.", url_for("owner_dashboard"))
        flash(f"{r.name} approved.", "success")
    elif action == "reject":
        r.is_approved, r.status = False, "rejected"
        notify(r.owner_id, "Restaurant not approved", f"{r.name} was not approved. Update your profile and contact support.",
               url_for("owner_profile"))
        flash(f"{r.name} rejected.", "info")
    else:
        abort(404)
    db.session.commit()
    return back("admin_restaurants")


@app.route("/admin/riders")
@admin_only
def admin_riders():
    riders = User.query.filter_by(role="rider").order_by(User.created_at.desc()).all()
    stats = {rid: (cnt, earned) for rid, cnt, earned in db.session.query(
        Order.rider_id, func.count(Order.id), func.coalesce(func.sum(Order.rider_fee), 0))
        .filter(Order.status == "delivered", Order.rider_id.isnot(None)).group_by(Order.rider_id).all()}
    active = {rid: cnt for rid, cnt in db.session.query(Order.rider_id, func.count(Order.id))
              .filter(Order.rider_id.isnot(None), ~Order.status.in_(["delivered", "cancelled"])).group_by(Order.rider_id).all()}
    return render_template("admin/riders.html", riders=riders, stats=stats, active=active)


# ---- orders, proofs, transactions --------------------------------------------------------
@app.route("/admin/orders")
@admin_only
def admin_orders():
    status, q = request.args.get("status", ""), clean(request.args.get("q"), 20)
    query = Order.query
    if status in STATUS_LABEL:
        query = query.filter_by(status=status)
    if q.lstrip("#").isdigit():
        query = query.filter_by(id=int(q.lstrip("#")))
    pagination = query.order_by(Order.created_at.desc()).paginate(page=_page(), per_page=20, error_out=False)
    flagged = {f.order_id for f in FraudFlag.query.filter_by(status="open").all()}
    return render_template("admin/orders.html", pagination=pagination, status=status, q=q, flagged=flagged)


@app.route("/admin/proofs")
@admin_only
def admin_proofs():
    status = request.args.get("status", "pending")
    query = PaymentProof.query
    if status in ("pending", "approved", "rejected"):
        query = query.filter_by(status=status)
    pagination = query.order_by(PaymentProof.uploaded_at.desc()).paginate(page=_page(), per_page=12, error_out=False)
    return render_template("admin/proofs.html", pagination=pagination, status=status)


@app.route("/admin/transactions")
@admin_only
def admin_transactions():
    kind = request.args.get("type", "orders")
    sums = db.session.query(func.coalesce(func.sum(Order.total_amount), 0), func.coalesce(func.sum(Order.commission), 0),
                            func.coalesce(func.sum(Order.service_charge), 0), func.coalesce(func.sum(Order.rider_fee), 0)) \
        .filter(Order.status == "delivered").one()
    ad_total = db.session.query(func.coalesce(func.sum(Ad.amount), 0)).filter(Ad.status == "approved").scalar()
    summary = {"gmv": sums[0], "commission": sums[1], "service": sums[2], "rider_payouts": sums[3], "ads": ad_total,
               "platform": sums[1] + sums[2] + ad_total - sums[3]}
    if kind == "ads":
        pagination = Ad.query.order_by(Ad.created_at.desc()).paginate(page=_page(), per_page=20, error_out=False)
    else:
        kind = "orders"
        pagination = Payment.query.order_by(Payment.created_at.desc()).paginate(page=_page(), per_page=20, error_out=False)
    return render_template("admin/transactions.html", pagination=pagination, kind=kind, summary=summary)


# ---- categories --------------------------------------------------------------------------
@app.route("/admin/categories", methods=["GET", "POST"])
@admin_only
def admin_categories():
    if request.method == "POST":
        name = clean(request.form.get("name"), 50)
        if len(name) < 2:
            flash("Enter a category name.", "error")
        elif Category.query.filter(func.lower(Category.name) == name.lower()).first():
            flash("That category already exists.", "error")
        else:
            db.session.add(Category(name=name))
            db.session.commit()
            flash(f"Category '{name}' added.", "success")
        return redirect(url_for("admin_categories"))
    usage = dict(db.session.query(FoodItem.category, func.count(FoodItem.id)).group_by(FoodItem.category).all())
    return render_template("admin/categories.html", categories=Category.query.order_by(Category.name).all(), usage=usage)


@app.route("/admin/categories/<int:category_id>/rename", methods=["POST"])
@admin_only
def admin_category_rename(category_id):
    cat = db.session.get(Category, category_id) or abort(404)
    name = clean(request.form.get("name"), 50)
    clash = Category.query.filter(func.lower(Category.name) == name.lower(), Category.id != cat.id).first()
    if len(name) < 2 or clash:
        flash("Enter a unique category name.", "error")
    else:
        FoodItem.query.filter_by(category=cat.name).update({"category": name})
        cat.name = name
        db.session.commit()
        flash("Category renamed.", "success")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@admin_only
def admin_category_delete(category_id):
    cat = db.session.get(Category, category_id) or abort(404)
    if FoodItem.query.filter_by(category=cat.name).count():
        flash("This category is used by dishes. Rename it instead of deleting it.", "error")
    else:
        db.session.delete(cat)
        db.session.commit()
        flash("Category deleted.", "info")
    return redirect(url_for("admin_categories"))


# ---- fraud, ads, messages ----------------------------------------------------------------
@app.route("/admin/fraud")
@admin_only
def admin_fraud():
    flags = FraudFlag.query.order_by((FraudFlag.status == "open").desc(), FraudFlag.created_at.desc()).limit(200).all()
    return render_template("admin/fraud.html", flags=flags)


@app.route("/admin/fraud/scan", methods=["POST"])
@admin_only
def admin_fraud_scan():
    created = scan_all_orders_for_fraud()
    db.session.commit()
    flash(f"Scan complete: {created} new alert(s) found." if created else "Scan complete: no new suspicious activity.",
          "success" if not created else "info")
    return redirect(url_for("admin_fraud"))


@app.route("/admin/fraud/<int:flag_id>/review", methods=["POST"])
@admin_only
def admin_fraud_review(flag_id):
    flag = db.session.get(FraudFlag, flag_id) or abort(404)
    flag.status = "reviewed"
    db.session.commit()
    flash("Alert marked as reviewed.", "success")
    return redirect(url_for("admin_fraud"))


@app.route("/admin/ads")
@admin_only
def admin_ads():
    ads = Ad.query.order_by((Ad.status == "pending").desc(), Ad.created_at.desc()).limit(100).all()
    return render_template("admin/ads.html", ads=ads, price=get_int("ad_price_per_week"))


@app.route("/admin/ads/<int:ad_id>/<decision>", methods=["POST"])
@admin_only
def admin_ad_decide(ad_id, decision):
    ad = db.session.get(Ad, ad_id) or abort(404)
    if ad.status != "pending" or decision not in ("approve", "reject"):
        flash("This ad request was already reviewed.", "info")
        return redirect(url_for("admin_ads"))
    if decision == "approve":
        now = utcnow()
        later = db.session.query(func.max(Ad.ends_at)).filter(Ad.restaurant_id == ad.restaurant_id, Ad.status == "approved").scalar()
        ad.starts_at = later if later and later > now else now
        ad.ends_at = ad.starts_at + timedelta(weeks=ad.weeks)
        ad.status = "approved"
        notify(ad.restaurant.owner_id, "Your sponsored ad is approved",
               f"{ad.restaurant.name} will be featured at the top until {ad.ends_at.strftime('%d %b %Y')}.", url_for("owner_ads"))
        flash("Ad approved and scheduled.", "success")
    else:
        ad.status = "rejected"
        notify(ad.restaurant.owner_id, "Sponsored ad rejected", "We could not verify your ad payment. Please resubmit.", url_for("owner_ads"))
        flash("Ad request rejected.", "info")
    db.session.commit()
    return redirect(url_for("admin_ads"))


@app.route("/admin/messages")
@admin_only
def admin_messages():
    items = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(200).all()
    unread = {m.id for m in items if not m.is_read}
    ContactMessage.query.filter_by(is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("admin/messages.html", items=items, unread=unread)


@app.route("/admin/messages/<int:message_id>/delete", methods=["POST"])
@admin_only
def admin_message_delete(message_id):
    msg = db.session.get(ContactMessage, message_id) or abort(404)
    db.session.delete(msg)
    db.session.commit()
    flash("Message deleted.", "info")
    return redirect(url_for("admin_messages"))


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_only
def admin_settings():
    if request.method == "POST":
        section = request.form.get("section")
        if section == "pricing":
            pct, service, rider_fee = to_float(request.form.get("commission_percent")), \
                to_int(request.form.get("service_charge"), -1, -1), to_int(request.form.get("rider_fee"), -1, -1)
            if pct is None or not 0 <= pct <= 50 or service < 0 or rider_fee < 0:
                flash("Commission must be 0-50% and the charges must be zero or more.", "error")
            else:
                set_setting("commission_percent", round(pct, 2))
                set_setting("service_charge", service)
                set_setting("rider_fee", rider_fee)
                flash("Pricing saved. New orders use these values.", "success")
        elif section == "ads":
            price = to_int(request.form.get("ad_price_per_week"), -1, -1)
            if price < 0:
                flash("Enter the weekly ad price.", "error")
            else:
                set_setting("ad_price_per_week", price)
                flash("Sponsored ad price saved.", "success")
        elif section == "bank":
            number = clean(request.form.get("admin_account_number"), 30)
            if number and not re.fullmatch(r"[0-9]{6,20}", number):
                flash("The account number should contain digits only.", "error")
            else:
                set_setting("admin_bank_name", clean(request.form.get("admin_bank_name"), 100))
                set_setting("admin_account_name", clean(request.form.get("admin_account_name"), 100))
                set_setting("admin_account_number", number)
                flash("Bank details saved. Restaurants see them when paying for ads.", "success")
        elif section == "contact":
            email = clean(request.form.get("contact_email"), 100)
            if email and not valid_email(email):
                flash("Enter a valid contact email.", "error")
            else:
                set_setting("contact_email", email)
                set_setting("contact_phone", clean(request.form.get("contact_phone"), 30))
                set_setting("contact_address", clean(request.form.get("contact_address"), 200))
                flash("Contact details saved.", "success")
        else:
            abort(400)
        db.session.commit()
        return redirect(url_for("admin_settings"))
    values = {k: get_setting(k) for k in DEFAULT_SETTINGS}
    return render_template("admin/settings.html", s=values)


# --------------------------------------------------------------------------------------
# Errors, seed data, entry point
# --------------------------------------------------------------------------------------
@app.errorhandler(403)
def forbidden(_):
    return render_template("errors.html", code=403, title="Access denied",
                           text="Your account does not have permission to open this page."), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("errors.html", code=404, title="Page not found",
                           text="The page you are looking for does not exist or was moved."), 404


@app.errorhandler(413)
def too_large(_):
    if wants_json():
        return jsonify(ok=False, message="That file is too large (max 5 MB)."), 413
    flash("That file is too large. Please upload an image under 5 MB.", "error")
    return redirect(request.referrer if request.referrer and is_safe_url(request.referrer) else url_for("index"))


@app.errorhandler(500)
def server_error(_):
    db.session.rollback()
    return render_template("errors.html", code=500, title="Something went wrong",
                           text="We hit an unexpected problem. Please try again in a moment."), 500


def seed_defaults():
    """Create missing tables and first-run data. Safe to run on every start."""
    db.create_all()
    for key, value in DEFAULT_SETTINGS.items():
        if not db.session.get(Setting, key):
            db.session.add(Setting(setting_key=key, setting_value=value))
    for name in DEFAULT_CATEGORIES:
        if not Category.query.filter(func.lower(Category.name) == name.lower()).first():
            db.session.add(Category(name=name))
    if not User.query.filter_by(role="admin").first():
        db.session.add(User(name="SmartBite Admin", email=app.config["ADMIN_EMAIL"], role="admin",
                            password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]), phone="0000000000",
                            address="SmartBite HQ", must_change_password=True))
        print(f"[SmartBite] Admin account created: {app.config['ADMIN_EMAIL']} - you must change the password at first login.")
    db.session.commit()


with app.app_context():
    try:
        seed_defaults()
    except Exception as exc:  # database not reachable / not created yet
        print("\n[SmartBite] Could not connect to the database.\n"
              "  1) Create it:  CREATE DATABASE smartbite_db CHARACTER SET utf8mb4;\n"
              "  2) Import it:  mysql -u root -p smartbite_db < database.sql\n"
              "  3) Check DB_USER / DB_PASSWORD / DB_HOST in your .env file.\n"
              f"  Details: {exc}\n")
        raise

if __name__ == "__main__":
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=app.config["DEBUG"])
