from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    Category,
    Customer,
    Employee,
    Expense,
    ExpenseCategory,
    Inventory,
    LedgerEntry,
    Payment,
    PayrollEntry,
    Permission,
    Product,
    Purchase,
    PurchaseItem,
    PurchaseReturn,
    Role,
    RolePermission,
    Sale,
    SaleItem,
    SaleReturn,
    StockMovement,
    Supplier,
    Unit,
)

main_bp = Blueprint("main", __name__)


def user_has_permission(permission_code):
    if not current_user.is_authenticated:
        return False
    if current_user.role is None:
        return False
    return any(
        role_permission.permission.code == permission_code
        for role_permission in current_user.role.role_permissions
    )


def can_manage_finance():
    return user_has_permission("manage_sales") or user_has_permission("manage_purchases")


def get_business_totals(business):
    sales_total = db.session.query(db.func.coalesce(db.func.sum(Sale.total), 0)).filter_by(business_id=business.id).scalar() or 0
    purchases_total = db.session.query(db.func.coalesce(db.func.sum(Purchase.total), 0)).filter_by(business_id=business.id).scalar() or 0
    expenses_total = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).filter_by(business_id=business.id).scalar() or 0

    inventory_items = Inventory.query.filter_by(business_id=business.id).all()
    stock_alerts = 0
    for inventory_item in inventory_items:
        if inventory_item.product and inventory_item.product.min_stock is not None and inventory_item.quantity <= inventory_item.product.min_stock:
            stock_alerts += 1

    profit = float(sales_total) - float(purchases_total) - float(expenses_total)

    return {
        "sales_total": float(sales_total),
        "purchases_total": float(purchases_total),
        "expenses_total": float(expenses_total),
        "profit": profit,
        "stock_alerts": stock_alerts,
    }


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    business = current_user.business
    metrics = get_business_totals(business)
    return render_template(
        "dashboard.html",
        business=business,
        sales_total=metrics["sales_total"],
        purchases_total=metrics["purchases_total"],
        expenses_total=metrics["expenses_total"],
        profit=metrics["profit"],
        stock_alerts=metrics["stock_alerts"],
    )


@main_bp.route("/reports")
@login_required
def reports():
    if not user_has_permission("view_reports"):
        flash("You do not have access to reports.", "danger")
        return redirect(url_for("main.dashboard"))

    business = current_user.business
    metrics = get_business_totals(business)
    sales = Sale.query.filter_by(business_id=business.id).order_by(Sale.sold_at.desc()).limit(10).all()
    purchases = Purchase.query.filter_by(business_id=business.id).order_by(Purchase.purchased_at.desc()).limit(10).all()
    expenses = Expense.query.filter_by(business_id=business.id).order_by(Expense.expense_date.desc()).limit(10).all()
    low_stock = [
        inventory_item
        for inventory_item in Inventory.query.filter_by(business_id=business.id).all()
        if inventory_item.product and inventory_item.product.min_stock is not None and inventory_item.quantity <= inventory_item.product.min_stock
    ]

    return render_template(
        "reports.html",
        business=business,
        metrics=metrics,
        sales=sales,
        purchases=purchases,
        expenses=expenses,
        low_stock=low_stock,
    )


def add_ledger_entry(business_id, entry_type, amount, direction="debit", reference_type=None, reference_id=None, account_type="cash", notes=None):
    if amount is None:
        amount = 0
    db.session.add(
        LedgerEntry(
            business_id=business_id,
            entry_type=entry_type,
            amount=float(amount),
            direction=direction,
            reference_type=reference_type,
            reference_id=reference_id,
            account_type=account_type,
            notes=notes,
        )
    )


@main_bp.route("/ledger")
@login_required
def ledger():
    if not user_has_permission("view_reports"):
        flash("You do not have access to the ledger.", "danger")
        return redirect(url_for("main.dashboard"))

    entries = LedgerEntry.query.filter_by(business_id=current_user.business_id).order_by(LedgerEntry.created_at.desc()).all()
    return render_template("ledger.html", entries=entries)


@main_bp.route("/returns", methods=["GET", "POST"])
@login_required
def returns():
    if not can_manage_finance():
        flash("You do not have access to returns.", "danger")
        return redirect(url_for("main.dashboard"))

    business = current_user.business
    sales = Sale.query.filter_by(business_id=business.id).all()
    purchases = Purchase.query.filter_by(business_id=business.id).all()

    if request.method == "POST":
        return_type = request.form.get("return_type")
        reference_id = request.form.get("reference_id")
        product_id = request.form.get("product_id")
        quantity = float(request.form.get("quantity") or 0)
        reason = request.form.get("reason", "return").strip()

        if not return_type or not reference_id or not product_id or quantity <= 0:
            flash("Please provide a valid return record.", "danger")
            return render_template("returns.html", sales=sales, purchases=purchases)

        if return_type == "sale":
            sale = Sale.query.filter_by(id=int(reference_id), business_id=business.id).first_or_404()
            sale_item = SaleItem.query.filter_by(sale_id=sale.id, product_id=int(product_id)).first()
            if sale_item is None:
                flash("This sale does not include the selected product.", "danger")
                return render_template("returns.html", sales=sales, purchases=purchases)
            total = quantity * sale_item.unit_price
            db.session.add(
                SaleReturn(
                    business_id=business.id,
                    sale_id=sale.id,
                    product_id=int(product_id),
                    quantity=quantity,
                    unit_price=sale_item.unit_price,
                    reason=reason,
                    total=total,
                )
            )
            inventory = Inventory.query.filter_by(business_id=business.id, product_id=int(product_id)).first()
            if inventory is not None:
                inventory.quantity += quantity
            sale.total = max(0.0, sale.total - total)
            sale.due = max(0.0, sale.due - total)
            add_ledger_entry(business.id, "sale_return", total, "debit", "sale", sale.id, "receivable", reason)
        else:
            purchase = Purchase.query.filter_by(id=int(reference_id), business_id=business.id).first_or_404()
            purchase_item = PurchaseItem.query.filter_by(purchase_id=purchase.id, product_id=int(product_id)).first()
            if purchase_item is None:
                flash("This purchase does not include the selected product.", "danger")
                return render_template("returns.html", sales=sales, purchases=purchases)
            total = quantity * purchase_item.unit_price
            db.session.add(
                PurchaseReturn(
                    business_id=business.id,
                    purchase_id=purchase.id,
                    product_id=int(product_id),
                    quantity=quantity,
                    unit_price=purchase_item.unit_price,
                    reason=reason,
                    total=total,
                )
            )
            inventory = Inventory.query.filter_by(business_id=business.id, product_id=int(product_id)).first()
            if inventory is not None:
                inventory.quantity = max(0.0, inventory.quantity - quantity)
            purchase.total = max(0.0, purchase.total - total)
            purchase.due = max(0.0, purchase.due - total)
            add_ledger_entry(business.id, "purchase_return", total, "credit", "purchase", purchase.id, "payable", reason)

        db.session.commit()
        flash("Return recorded successfully.", "success")
        return redirect(url_for("main.returns"))

    return render_template("returns.html", sales=sales, purchases=purchases)


@main_bp.route("/employees", methods=["GET", "POST"])
@login_required
def employees():
    if not user_has_permission("manage_users"):
        flash("You do not have access to employee records.", "danger")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "Staff").strip() or "Staff"
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        salary = float(request.form.get("salary") or 0)

        if not name:
            flash("Employee name is required.", "danger")
            return render_template("employees.html", employees=Employee.query.filter_by(business_id=current_user.business_id).all())

        db.session.add(
            Employee(
                business_id=current_user.business_id,
                name=name,
                role=role,
                phone=phone,
                email=email,
                salary=salary,
            )
        )
        db.session.commit()
        flash("Employee added successfully.", "success")
        return redirect(url_for("main.employees"))

    return render_template("employees.html", employees=Employee.query.filter_by(business_id=current_user.business_id).all())


@main_bp.route("/payroll", methods=["GET", "POST"])
@login_required
def payroll():
    if not user_has_permission("manage_users"):
        flash("You do not have access to payroll.", "danger")
        return redirect(url_for("main.dashboard"))

    employees = Employee.query.filter_by(business_id=current_user.business_id).all()

    if request.method == "POST":
        employee_id = request.form.get("employee_id")
        payroll_month = request.form.get("payroll_month", "").strip()
        payroll_year = int(request.form.get("payroll_year") or 2026)
        base_salary = float(request.form.get("base_salary") or 0)
        allowances = float(request.form.get("allowances") or 0)
        deductions = float(request.form.get("deductions") or 0)

        if not employee_id or not payroll_month:
            flash("Employee and month are required.", "danger")
            return render_template("payroll.html", employees=employees, entries=PayrollEntry.query.filter_by(business_id=current_user.business_id).order_by(PayrollEntry.payroll_year.desc(), PayrollEntry.payroll_month.desc()).all())

        net_salary = base_salary + allowances - deductions
        entry = PayrollEntry(
            business_id=current_user.business_id,
            employee_id=int(employee_id),
            payroll_month=payroll_month,
            payroll_year=payroll_year,
            base_salary=base_salary,
            allowances=allowances,
            deductions=deductions,
            net_salary=net_salary,
            status="paid" if net_salary > 0 else "pending",
        )
        db.session.add(entry)
        db.session.commit()
        flash("Payroll entry recorded successfully.", "success")
        return redirect(url_for("main.payroll"))

    return render_template("payroll.html", employees=employees, entries=PayrollEntry.query.filter_by(business_id=current_user.business_id).order_by(PayrollEntry.payroll_year.desc(), PayrollEntry.payroll_month.desc()).all())


@main_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if not user_has_permission("manage_business"):
        flash("You do not have access to business settings.", "danger")
        return redirect(url_for("main.dashboard"))

    business = current_user.business

    if request.method == "POST":
        business.name = request.form.get("name", business.name).strip() or business.name
        business.business_type = request.form.get("business_type", business.business_type).strip() or business.business_type
        business.phone = request.form.get("phone", business.phone or "").strip()
        business.email = request.form.get("email", business.email or "").strip()
        business.address = request.form.get("address", business.address or "").strip()
        business.currency = request.form.get("currency", business.currency or "PKR").strip() or "PKR"
        business.tax_rate = float(request.form.get("tax_rate", business.tax_rate or 0) or 0)
        db.session.commit()
        flash("Business settings updated successfully.", "success")
        return redirect(url_for("main.settings"))

    return render_template("settings.html", business=business)


@main_bp.route("/roles", methods=["GET", "POST"])
@login_required
def roles():
    if not user_has_permission("manage_users"):
        flash("You do not have access to role management.", "danger")
        return redirect(url_for("main.dashboard"))

    permissions = Permission.query.order_by(Permission.code).all()
    business_roles = current_user.business.roles

    if request.method == "POST":
        role_name = request.form.get("role_name", "").strip()
        selected_permissions = request.form.getlist("permissions")
        if not role_name:
            flash("Role name is required.", "danger")
            return render_template("roles.html", permissions=permissions, roles=business_roles)

        role = Role(business_id=current_user.business_id, name=role_name)
        db.session.add(role)
        db.session.flush()

        for permission_id in selected_permissions:
            db.session.add(RolePermission(role_id=role.id, permission_id=int(permission_id)))

        db.session.commit()
        flash(f"Role '{role_name}' created successfully.", "success")
        return redirect(url_for("main.roles"))

    return render_template("roles.html", permissions=permissions, roles=business_roles)


@main_bp.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if not user_has_permission("manage_products"):
        flash("You do not have access to products.", "danger")
        return redirect(url_for("main.dashboard"))

    business = current_user.business
    categories = Category.query.filter_by(business_id=business.id).order_by(Category.name).all()
    units = Unit.query.filter_by(business_id=business.id).order_by(Unit.name).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip()
        product_type = request.form.get("product_type", "product")
        purchase_price = float(request.form.get("purchase_price") or 0)
        sale_price = float(request.form.get("sale_price") or 0)
        tax_rate = float(request.form.get("tax_rate") or 0)
        min_stock = float(request.form.get("min_stock") or 0)
        category_name = request.form.get("category_name", "").strip()
        unit_name = request.form.get("unit_name", "").strip()

        if not name or not sku:
            flash("Product name and SKU are required.", "danger")
            return render_template("products.html", products=business.products, categories=categories, units=units, selected=None)

        category = None
        if category_name:
            category = Category.query.filter_by(business_id=business.id, name=category_name).first()
            if category is None:
                category = Category(business_id=business.id, name=category_name)
                db.session.add(category)
                db.session.flush()

        category_id = request.form.get("category_id")
        if category_id and category_id != "":
            category = Category.query.filter_by(id=int(category_id), business_id=business.id).first()

        unit = None
        if unit_name:
            unit = Unit.query.filter_by(business_id=business.id, name=unit_name).first()
            if unit is None:
                unit = Unit(business_id=business.id, name=unit_name)
                db.session.add(unit)
                db.session.flush()

        unit_id = request.form.get("unit_id")
        if unit_id and unit_id != "":
            unit = Unit.query.filter_by(id=int(unit_id), business_id=business.id).first()

        if Product.query.filter_by(business_id=business.id, sku=sku).first():
            flash("A product with this SKU already exists in this business.", "warning")
            return render_template("products.html", products=business.products, categories=categories, units=units, selected=None)

        product = Product(
            business_id=business.id,
            category_id=category.id if category else None,
            unit_id=unit.id if unit else None,
            name=name,
            sku=sku,
            product_type=product_type,
            purchase_price=purchase_price,
            sale_price=sale_price,
            tax_rate=tax_rate,
            min_stock=min_stock,
        )
        db.session.add(product)
        db.session.flush()

        inventory = Inventory.query.filter_by(business_id=business.id, product_id=product.id).first()
        if inventory is None:
            db.session.add(Inventory(business_id=business.id, product_id=product.id, quantity=0))

        db.session.commit()
        flash("Product created successfully.", "success")
        return redirect(url_for("main.products"))

    return render_template("products.html", products=business.products, categories=categories, units=units, selected=None)


@main_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    if not user_has_permission("manage_products"):
        flash("You do not have access to products.", "danger")
        return redirect(url_for("main.dashboard"))

    product = Product.query.filter_by(id=product_id, business_id=current_user.business_id).first_or_404()
    categories = Category.query.filter_by(business_id=current_user.business_id).order_by(Category.name).all()
    units = Unit.query.filter_by(business_id=current_user.business_id).order_by(Unit.name).all()

    if request.method == "POST":
        product.name = request.form.get("name", product.name).strip() or product.name
        product.sku = request.form.get("sku", product.sku).strip() or product.sku
        product.product_type = request.form.get("product_type", product.product_type)
        product.purchase_price = float(request.form.get("purchase_price") or product.purchase_price)
        product.sale_price = float(request.form.get("sale_price") or product.sale_price)
        product.tax_rate = float(request.form.get("tax_rate") or product.tax_rate)
        product.min_stock = float(request.form.get("min_stock") or product.min_stock)

        category_id = request.form.get("category_id")
        if category_id:
            product.category_id = int(category_id)
        unit_id = request.form.get("unit_id")
        if unit_id:
            product.unit_id = int(unit_id)

        db.session.commit()
        flash("Product updated successfully.", "success")
        return redirect(url_for("main.products"))

    return render_template("products.html", products=current_user.business.products, categories=categories, units=units, selected=product)


@main_bp.route("/inventory")
@login_required
def inventory():
    if not user_has_permission("manage_inventory"):
        flash("You do not have access to inventory.", "danger")
        return redirect(url_for("main.dashboard"))

    inventory_items = Inventory.query.filter_by(business_id=current_user.business_id).all()
    movement_logs = StockMovement.query.filter_by(business_id=current_user.business_id).order_by(StockMovement.created_at.desc()).limit(20).all()
    return render_template("inventory.html", inventory_items=inventory_items, movement_logs=movement_logs)


@main_bp.route("/inventory/adjust", methods=["GET", "POST"])
@login_required
def adjust_inventory():
    if not user_has_permission("manage_inventory"):
        flash("You do not have access to inventory.", "danger")
        return redirect(url_for("main.dashboard"))

    products = Product.query.filter_by(business_id=current_user.business_id).all()

    if request.method == "POST":
        product_id = request.form.get("product_id")
        quantity = float(request.form.get("quantity") or 0)
        movement_type = request.form.get("movement_type", "adjustment")
        reference_type = request.form.get("reference_type", "manual")
        if not product_id or quantity <= 0:
            flash("Please select a product and enter a positive quantity.", "danger")
            return render_template("inventory_adjust.html", products=products)

        product = Product.query.filter_by(id=int(product_id), business_id=current_user.business_id).first_or_404()
        inventory = Inventory.query.filter_by(business_id=current_user.business_id, product_id=product.id).first()
        if inventory is None:
            inventory = Inventory(business_id=current_user.business_id, product_id=product.id, quantity=0)
            db.session.add(inventory)
        if movement_type == "stock_in":
            inventory.quantity += quantity
        else:
            inventory.quantity -= quantity

        stock_move = StockMovement(
            business_id=current_user.business_id,
            product_id=product.id,
            movement_type=movement_type,
            quantity=quantity if movement_type == "stock_in" else -quantity,
            reference_type=reference_type,
            reference_id=None,
            created_by=current_user.id,
        )
        db.session.add(stock_move)
        db.session.commit()
        flash("Inventory updated successfully.", "success")
        return redirect(url_for("main.inventory"))

    return render_template("inventory_adjust.html", products=products)


@main_bp.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    if not user_has_permission("manage_sales"):
        flash("You do not have access to customer records.", "danger")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        opening_balance = float(request.form.get("opening_balance") or 0)

        if not name:
            flash("Customer name is required.", "danger")
            return render_template("customers.html", customers=Customer.query.filter_by(business_id=current_user.business_id).all())

        db.session.add(
            Customer(
                business_id=current_user.business_id,
                name=name,
                phone=phone,
                email=email,
                address=address,
                opening_balance=opening_balance,
            )
        )
        db.session.commit()
        flash("Customer added successfully.", "success")
        return redirect(url_for("main.customers"))

    return render_template("customers.html", customers=Customer.query.filter_by(business_id=current_user.business_id).all())


@main_bp.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers():
    if not user_has_permission("manage_sales"):
        flash("You do not have access to supplier records.", "danger")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        opening_balance = float(request.form.get("opening_balance") or 0)

        if not name:
            flash("Supplier name is required.", "danger")
            return render_template("suppliers.html", suppliers=Supplier.query.filter_by(business_id=current_user.business_id).all())

        db.session.add(
            Supplier(
                business_id=current_user.business_id,
                name=name,
                phone=phone,
                email=email,
                address=address,
                opening_balance=opening_balance,
            )
        )
        db.session.commit()
        flash("Supplier added successfully.", "success")
        return redirect(url_for("main.suppliers"))

    return render_template("suppliers.html", suppliers=Supplier.query.filter_by(business_id=current_user.business_id).all())


@main_bp.route("/purchases", methods=["GET", "POST"])
@login_required
def purchases():
    if not user_has_permission("manage_purchases"):
        flash("You do not have access to purchases.", "danger")
        return redirect(url_for("main.dashboard"))

    business = current_user.business
    suppliers = Supplier.query.filter_by(business_id=business.id).all()
    products = Product.query.filter_by(business_id=business.id).all()

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id")
        product_id = request.form.get("product_id")
        quantity = float(request.form.get("quantity") or 0)
        unit_price = float(request.form.get("unit_price") or 0)

        if not supplier_id or not product_id or quantity <= 0:
            flash("Supplier, product and quantity are required.", "danger")
            return render_template("purchases.html", purchases=Purchase.query.filter_by(business_id=business.id).all(), suppliers=suppliers, products=products)

        supplier = Supplier.query.filter_by(id=int(supplier_id), business_id=business.id).first_or_404()
        product = Product.query.filter_by(id=int(product_id), business_id=business.id).first_or_404()

        subtotal = quantity * unit_price
        tax = subtotal * (product.tax_rate / 100 if product.tax_rate else 0)
        total = subtotal + tax

        purchase = Purchase(
            business_id=business.id,
            supplier_id=supplier.id,
            purchase_no=f"PO-{business.id}-{Purchase.query.filter_by(business_id=business.id).count() + 1:04d}",
            subtotal=subtotal,
            discount=0,
            tax=tax,
            total=total,
            paid=0,
            due=total,
            status="pending",
            created_by=current_user.id,
        )
        db.session.add(purchase)
        db.session.flush()

        db.session.add(
            PurchaseItem(
                purchase_id=purchase.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price,
                discount=0,
                tax=tax,
                line_total=total,
            )
        )

        inventory = Inventory.query.filter_by(business_id=business.id, product_id=product.id).first()
        if inventory is None:
            inventory = Inventory(business_id=business.id, product_id=product.id, quantity=0)
            db.session.add(inventory)
        inventory.quantity += quantity

        db.session.add(
            StockMovement(
                business_id=business.id,
                product_id=product.id,
                movement_type="stock_in",
                quantity=quantity,
                reference_type="purchase",
                reference_id=purchase.id,
                created_by=current_user.id,
            )
        )

        add_ledger_entry(business.id, "purchase", total, "debit", "purchase", purchase.id, "payable", f"Purchase {purchase.purchase_no}")
        db.session.commit()
        flash("Purchase created successfully.", "success")
        return redirect(url_for("main.purchases"))

    return render_template("purchases.html", purchases=Purchase.query.filter_by(business_id=business.id).all(), suppliers=suppliers, products=products)


@main_bp.route("/sales", methods=["GET", "POST"])
@login_required
def sales():
    if not user_has_permission("manage_sales"):
        flash("You do not have access to sales.", "danger")
        return redirect(url_for("main.dashboard"))

    business = current_user.business
    customers = Customer.query.filter_by(business_id=business.id).all()
    products = Product.query.filter_by(business_id=business.id).all()

    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        product_id = request.form.get("product_id")
        quantity = float(request.form.get("quantity") or 0)
        unit_price = float(request.form.get("unit_price") or 0)

        if not customer_id or not product_id or quantity <= 0:
            flash("Customer, product and quantity are required.", "danger")
            return render_template("sales.html", sales=Sale.query.filter_by(business_id=business.id).all(), customers=customers, products=products)

        customer = Customer.query.filter_by(id=int(customer_id), business_id=business.id).first_or_404()
        product = Product.query.filter_by(id=int(product_id), business_id=business.id).first_or_404()

        if product.product_type != "service":
            inventory = Inventory.query.filter_by(business_id=business.id, product_id=product.id).first()
            if inventory is None or inventory.quantity < quantity:
                flash("Insufficient stock for this product.", "danger")
                return render_template("sales.html", sales=Sale.query.filter_by(business_id=business.id).all(), customers=customers, products=products)

        subtotal = quantity * unit_price
        tax = subtotal * (product.tax_rate / 100 if product.tax_rate else 0)
        total = subtotal + tax

        sale = Sale(
            business_id=business.id,
            customer_id=customer.id,
            invoice_no=f"INV-{business.id}-{Sale.query.filter_by(business_id=business.id).count() + 1:04d}",
            subtotal=subtotal,
            discount=0,
            tax=tax,
            total=total,
            paid=0,
            due=total,
            status="unpaid",
            created_by=current_user.id,
        )
        db.session.add(sale)
        db.session.flush()

        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            description=product.name,
            quantity=quantity,
            unit_price=unit_price,
            discount=0,
            tax=tax,
            line_total=total,
        )
        db.session.add(sale_item)

        if product.product_type != "service":
            inventory = Inventory.query.filter_by(business_id=business.id, product_id=product.id).first()
            inventory.quantity -= quantity
            db.session.add(
                StockMovement(
                    business_id=business.id,
                    product_id=product.id,
                    movement_type="stock_out",
                    quantity=-quantity,
                    reference_type="sale",
                    reference_id=sale.id,
                    created_by=current_user.id,
                )
            )

        add_ledger_entry(business.id, "sale", total, "credit", "sale", sale.id, "receivable", f"Invoice {sale.invoice_no}")
        db.session.commit()
        flash("Sale created successfully.", "success")
        return redirect(url_for("main.sale_invoice", sale_id=sale.id))

    return render_template("sales.html", sales=Sale.query.filter_by(business_id=business.id).all(), customers=customers, products=products)


@main_bp.route("/payments", methods=["GET", "POST"])
@login_required
def payments():
    if not can_manage_finance():
        flash("You do not have access to finance payments.", "danger")
        return redirect(url_for("main.dashboard"))

    business = current_user.business
    customers = Customer.query.filter_by(business_id=business.id).all()
    suppliers = Supplier.query.filter_by(business_id=business.id).all()
    sales = Sale.query.filter_by(business_id=business.id).all()
    purchases = Purchase.query.filter_by(business_id=business.id).all()

    if request.method == "POST":
        party_type = request.form.get("party_type", "customer")
        party_id = request.form.get("party_id")
        reference_type = request.form.get("reference_type", "sale")
        reference_id = request.form.get("reference_id")
        amount = float(request.form.get("amount") or 0)
        method = request.form.get("method", "cash")

        if not party_id or not amount or amount <= 0:
            flash("Please provide a party and valid payment amount.", "danger")
            return render_template("payments.html", customers=customers, suppliers=suppliers, sales=sales, purchases=purchases, payments=Payment.query.filter_by(business_id=business.id).order_by(Payment.paid_at.desc()).all())

        payment = Payment(
            business_id=business.id,
            party_type=party_type,
            party_id=int(party_id),
            reference_type=reference_type,
            reference_id=int(reference_id) if reference_id else None,
            amount=amount,
            method=method,
            created_by=current_user.id,
        )
        db.session.add(payment)
        add_ledger_entry(
            business.id,
            "payment",
            amount,
            "credit" if party_type == "customer" else "debit",
            reference_type,
            int(reference_id) if reference_id else None,
            "cash" if method == "cash" else "bank",
            f"{party_type.title()} payment",
        )

        if reference_type == "sale":
            sale = Sale.query.filter_by(id=int(reference_id), business_id=business.id).first()
            if sale:
                sale.paid += amount
                sale.due = max(0.0, sale.total - sale.paid)
                sale.status = "paid" if sale.due == 0 else "partial"
        elif reference_type == "purchase":
            purchase = Purchase.query.filter_by(id=int(reference_id), business_id=business.id).first()
            if purchase:
                purchase.paid += amount
                purchase.due = max(0.0, purchase.total - purchase.paid)
                purchase.status = "paid" if purchase.due == 0 else "partial"

        db.session.commit()
        flash("Payment recorded successfully.", "success")
        return redirect(url_for("main.payments"))

    return render_template("payments.html", customers=customers, suppliers=suppliers, sales=sales, purchases=purchases, payments=Payment.query.filter_by(business_id=business.id).order_by(Payment.paid_at.desc()).all())


@main_bp.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():
    if not can_manage_finance():
        flash("You do not have access to expenses.", "danger")
        return redirect(url_for("main.dashboard"))

    business = current_user.business
    categories = ExpenseCategory.query.filter_by(business_id=business.id).order_by(ExpenseCategory.name).all()

    if request.method == "POST":
        category_name = request.form.get("category_name", "").strip()
        description = request.form.get("description", "").strip()
        amount = float(request.form.get("amount") or 0)
        method = request.form.get("method", "cash")

        if not description or amount <= 0:
            flash("Expense description and amount are required.", "danger")
            return render_template("expenses.html", categories=categories, expenses=Expense.query.filter_by(business_id=business.id).order_by(Expense.expense_date.desc()).all())

        category = None
        category_id = request.form.get("category_id")
        if category_id:
            category = ExpenseCategory.query.filter_by(id=int(category_id), business_id=business.id).first()
        if not category and category_name:
            category = ExpenseCategory.query.filter_by(business_id=business.id, name=category_name).first()
            if category is None:
                category = ExpenseCategory(business_id=business.id, name=category_name)
                db.session.add(category)
                db.session.flush()

        if category is None:
            flash("Please choose or create an expense category.", "danger")
            return render_template("expenses.html", categories=categories, expenses=Expense.query.filter_by(business_id=business.id).order_by(Expense.expense_date.desc()).all())

        expense = Expense(
            business_id=business.id,
            category_id=category.id,
            description=description,
            amount=amount,
            method=method,
            created_by=current_user.id,
        )
        db.session.add(expense)
        db.session.flush()
        add_ledger_entry(business.id, "expense", amount, "debit", "expense", expense.id, method, description)
        db.session.commit()
        flash("Expense recorded successfully.", "success")
        return redirect(url_for("main.expenses"))

    return render_template("expenses.html", categories=categories, expenses=Expense.query.filter_by(business_id=business.id).order_by(Expense.expense_date.desc()).all())


@main_bp.route("/sales/<int:sale_id>/invoice")
@login_required
def sale_invoice(sale_id):
    sale = Sale.query.filter_by(id=sale_id, business_id=current_user.business_id).first_or_404()
    return render_template("invoice.html", sale=sale)
