from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from app import db


class Business(db.Model):
    __tablename__ = "businesses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    business_type = db.Column(db.String(100), nullable=False, default="General")
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    address = db.Column(db.String(255))
    currency = db.Column(db.String(20), default="PKR")
    tax_rate = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", back_populates="business", cascade="all, delete-orphan")
    products = db.relationship("Product", back_populates="business", cascade="all, delete-orphan")
    customers = db.relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    suppliers = db.relationship("Supplier", back_populates="business", cascade="all, delete-orphan")
    sales = db.relationship("Sale", back_populates="business", cascade="all, delete-orphan")
    purchases = db.relationship("Purchase", back_populates="business", cascade="all, delete-orphan")
    expenses = db.relationship("Expense", back_populates="business", cascade="all, delete-orphan")
    ledger_entries = db.relationship("LedgerEntry", backref="business", cascade="all, delete-orphan")
    employees = db.relationship("Employee", back_populates="business", cascade="all, delete-orphan")
    settings = db.relationship("Setting", back_populates="business", cascade="all, delete-orphan")


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)

    business = db.relationship("Business", backref="roles")
    users = db.relationship("User", back_populates="role")
    role_permissions = db.relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255))

    role_permissions = db.relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), nullable=False)

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role = db.relationship("Role", back_populates="role_permissions")
    permission = db.relationship("Permission", back_populates="role_permissions")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    business = db.relationship("Business", back_populates="users")
    role = db.relationship("Role", back_populates="users")

    def get_id(self):
        return str(self.id)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), default="active")

    business = db.relationship("Business", backref="categories")
    products = db.relationship("Product", back_populates="category")


class Unit(db.Model):
    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    symbol = db.Column(db.String(20))

    business = db.relationship("Business", backref="units")
    products = db.relationship("Product", back_populates="unit")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(80), nullable=False)
    product_type = db.Column(db.String(50), default="product")
    purchase_price = db.Column(db.Float, default=0.0)
    sale_price = db.Column(db.Float, default=0.0)
    tax_rate = db.Column(db.Float, default=0.0)
    min_stock = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="active")

    __table_args__ = (UniqueConstraint("business_id", "sku", name="uq_business_sku"),)

    business = db.relationship("Business", back_populates="products")
    category = db.relationship("Category", back_populates="products")
    unit = db.relationship("Unit", back_populates="products")
    inventory = db.relationship("Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan")
    stock_movements = db.relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")


class Inventory(db.Model):
    __tablename__ = "inventory"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, unique=True)
    quantity = db.Column(db.Float, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship("Product", back_populates="inventory")


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    movement_type = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product", back_populates="stock_movements")


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    address = db.Column(db.String(255))
    opening_balance = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="active")

    business = db.relationship("Business", back_populates="customers")
    sales = db.relationship("Sale", back_populates="customer")


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    address = db.Column(db.String(255))
    opening_balance = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="active")

    business = db.relationship("Business", back_populates="suppliers")
    purchases = db.relationship("Purchase", back_populates="supplier")


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    invoice_no = db.Column(db.String(50), nullable=False)
    subtotal = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    paid = db.Column(db.Float, default=0.0)
    due = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default="draft")
    sold_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    business = db.relationship("Business", back_populates="sales")
    customer = db.relationship("Customer", back_populates="sales")
    items = db.relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    line_total = db.Column(db.Float, default=0.0)

    sale = db.relationship("Sale", back_populates="items")


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    purchase_no = db.Column(db.String(50), nullable=False)
    subtotal = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    paid = db.Column(db.Float, default=0.0)
    due = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default="draft")
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    business = db.relationship("Business", back_populates="purchases")
    supplier = db.relationship("Supplier", back_populates="purchases")
    items = db.relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")


class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    line_total = db.Column(db.Float, default=0.0)

    purchase = db.relationship("Purchase", back_populates="items")


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    entry_type = db.Column(db.String(60), nullable=False)
    reference_type = db.Column(db.String(60), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    account_type = db.Column(db.String(60), default="cash")
    amount = db.Column(db.Float, default=0.0)
    direction = db.Column(db.String(20), default="debit")
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SaleReturn(db.Model):
    __tablename__ = "sale_returns"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    reason = db.Column(db.String(255), default="customer_return")
    total = db.Column(db.Float, default=0.0)
    returned_at = db.Column(db.DateTime, default=datetime.utcnow)


class PurchaseReturn(db.Model):
    __tablename__ = "purchase_returns"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    reason = db.Column(db.String(255), default="damaged_goods")
    total = db.Column(db.Float, default=0.0)
    returned_at = db.Column(db.DateTime, default=datetime.utcnow)


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(120), default="Staff")
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    salary = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="active")
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    business = db.relationship("Business", back_populates="employees")
    payroll_entries = db.relationship("PayrollEntry", back_populates="employee", cascade="all, delete-orphan")


class PayrollEntry(db.Model):
    __tablename__ = "payroll_entries"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    payroll_month = db.Column(db.String(20), nullable=False)
    payroll_year = db.Column(db.Integer, default=lambda: datetime.utcnow().year)
    base_salary = db.Column(db.Float, default=0.0)
    allowances = db.Column(db.Float, default=0.0)
    deductions = db.Column(db.Float, default=0.0)
    net_salary = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="pending")
    paid_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship("Employee", back_populates="payroll_entries")


class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)

    expenses = db.relationship("Expense", back_populates="category")


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("expense_categories.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50), default="cash")
    expense_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    business = db.relationship("Business", back_populates="expenses")
    category = db.relationship("ExpenseCategory", back_populates="expenses")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    party_type = db.Column(db.String(50), nullable=False)
    party_id = db.Column(db.Integer, nullable=False)
    reference_type = db.Column(db.String(60), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50), default="cash")
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    key = db.Column(db.String(120), nullable=False)
    value = db.Column(db.String(255), nullable=True)

    business = db.relationship("Business", back_populates="settings")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
