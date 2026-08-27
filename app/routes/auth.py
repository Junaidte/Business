from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import login_required, login_user, logout_user

from app import db, ensure_default_permissions
from app.models import Business, Permission, Role, RolePermission, User

bcrypt = Bcrypt()
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Login successful.", "success")
            return redirect(url_for("main.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip()
        business_type = request.form.get("business_type", "General").strip()
        owner_name = request.form.get("owner_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not all([business_name, owner_name, email, password]):
            flash("All fields are required.", "danger")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "warning")
            return render_template("auth/register.html")

        ensure_default_permissions()

        business = Business(name=business_name, business_type=business_type)
        db.session.add(business)
        db.session.flush()

        owner_role = Role(business_id=business.id, name="Owner")
        db.session.add(owner_role)
        db.session.flush()

        all_permissions = Permission.query.all()
        for permission in all_permissions:
            db.session.add(RolePermission(role_id=owner_role.id, permission_id=permission.id))

        user = User(
            business_id=business.id,
            role_id=owner_role.id,
            name=owner_name,
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        )
        db.session.add(user)
        db.session.commit()

        flash("Business account created successfully.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))
