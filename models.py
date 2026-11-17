"""SmartBite database models (Flask-SQLAlchemy)."""
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


ORDER_STATUSES = ("placed", "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("customer", "restaurant_owner", "rider", "admin", "staff", name="user_role"),
                     nullable=False, default="customer")
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    active = db.Column("is_active", db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    restaurant = db.relationship("Restaurant", back_populates="owner", uselist=False)
    staff_profile = db.relationship("StaffMember", back_populates="user", uselist=False)

    @property
    def is_active(self):  # Flask-Login hook
        return bool(self.active)


class Restaurant(db.Model):
    __tablename__ = "restaurants"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    image = db.Column(db.String(255))
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending | approved | rejected
    is_open = db.Column(db.Boolean, nullable=False, default=True)
    rating = db.Column(db.Float, default=0)
    rating_count = db.Column(db.Integer, default=0)
    delivery_time = db.Column(db.Integer, default=35)
    bank_name = db.Column(db.String(100))
    account_name = db.Column(db.String(100))
    account_number = db.Column(db.String(30))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=utcnow)

    owner = db.relationship("User", back_populates="restaurant")
    foods = db.relationship("FoodItem", back_populates="restaurant", cascade="all, delete-orphan")
    staff = db.relationship("StaffMember", back_populates="restaurant", cascade="all, delete-orphan")
    ads = db.relationship("Ad", back_populates="restaurant", cascade="all, delete-orphan")


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class FoodItem(db.Model):
    __tablename__ = "food_items"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50))
    image = db.Column(db.String(255))
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    restaurant = db.relationship("Restaurant", back_populates="foods")


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    subtotal = db.Column(db.Integer, nullable=False, default=0)
    total_amount = db.Column(db.Integer, nullable=False)
    service_charge = db.Column(db.Integer, nullable=False, default=0)
    commission = db.Column(db.Integer, nullable=False, default=0)
    rider_fee = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.Enum(*ORDER_STATUSES, name="order_status"), nullable=False, default="placed", index=True)
    rider_stage = db.Column(db.Enum("assigned", "picked", "on_the_way", "delivered", name="rider_stage"))
    payment_method = db.Column(db.String(20), nullable=False, default="cod")  # cod | online
    payment_status = db.Column(db.String(30), nullable=False, default="pending")
    paystack_ref = db.Column(db.String(100))
    delivery_address = db.Column(db.Text, nullable=False)
    customer_phone = db.Column(db.String(20))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    note = db.Column(db.String(255))
    is_packed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    delivered_at = db.Column(db.DateTime)

    customer = db.relationship("User", foreign_keys=[customer_id])
    rider = db.relationship("User", foreign_keys=[rider_id])
    restaurant = db.relationship("Restaurant")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = db.relationship("Payment", back_populates="order", uselist=False, cascade="all, delete-orphan")
    proofs = db.relationship("PaymentProof", back_populates="order", cascade="all, delete-orphan",
                             order_by="PaymentProof.uploaded_at.desc()")


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    food_id = db.Column(db.Integer, db.ForeignKey("food_items.id", ondelete="SET NULL"), nullable=True, index=True)
    food_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="items")


class CartItem(db.Model):
    __tablename__ = "cart"
    __table_args__ = (db.UniqueConstraint("customer_id", "food_id", name="uq_cart_customer_food"),)
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    food_id = db.Column(db.Integer, db.ForeignKey("food_items.id", ondelete="CASCADE"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    food = db.relationship("FoodItem")


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="SET NULL"), unique=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)

    customer = db.relationship("User")
    restaurant = db.relationship("Restaurant")


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    method = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    reference = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=utcnow)

    order = db.relationship("Order", back_populates="payment")


class PaymentProof(db.Model):
    __tablename__ = "payment_proofs"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Enum("pending", "approved", "rejected", name="proof_status"), nullable=False, default="pending")
    note = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = db.Column(db.DateTime)

    order = db.relationship("Order", back_populates="proofs")
    customer = db.relationship("User", foreign_keys=[customer_id])


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(500))
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "kind", "target_id", name="uq_favorite"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(12), nullable=False)  # food | restaurant
    target_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class StaffMember(db.Model):
    __tablename__ = "staff_members"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_role = db.Column(db.Enum("cook", "packager", name="staff_role"), nullable=False)
    monthly_salary = db.Column(db.Integer, nullable=False, default=0)
    hired_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", back_populates="staff_profile")
    restaurant = db.relationship("Restaurant", back_populates="staff")


class Ad(db.Model):
    __tablename__ = "ads"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    weeks = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    proof_image = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending | approved | rejected
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)

    restaurant = db.relationship("Restaurant", back_populates="ads")

    @property
    def is_live(self):
        now = utcnow()
        return self.status == "approved" and self.starts_at and self.ends_at and self.starts_at <= now <= self.ends_at


class Setting(db.Model):
    __tablename__ = "settings"
    setting_key = db.Column(db.String(50), primary_key=True)
    setting_value = db.Column(db.Text)


class FraudFlag(db.Model):
    __tablename__ = "fraud_flags"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")  # open | reviewed
    created_at = db.Column(db.DateTime, default=utcnow)

    order = db.relationship("Order")
    user = db.relationship("User")


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class RiderLocation(db.Model):
    """Latest GPS position shared by a rider for one assigned delivery."""
    __tablename__ = "rider_locations"
    __table_args__ = (db.UniqueConstraint("rider_id", "order_id", name="uq_rider_location_order"),)
    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    rider = db.relationship("User")
    order = db.relationship("Order")
