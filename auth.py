from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import new_id, now_ts
from emailer import send_verification_email

auth_bp = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.email = row["email"]
        self.name = row["name"]
        self.is_verified = bool(row["is_verified"])


@login_manager.user_loader
def load_user(user_id):
    row = db.get("users", id=user_id)
    return User(row) if row else None


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not email or not name or not password:
            flash("All fields are required.", "error")
            return render_template("register.html", email=email, name=name)

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html", email=email, name=name)

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html", email=email, name=name)

        if db.get("users", email=email):
            flash("An account with that email already exists.", "error")
            return render_template("register.html", email=email, name=name)

        token = new_id()
        db.insert(
            "users",
            id=new_id(),
            email=email,
            password_hash=generate_password_hash(password),
            name=name,
            is_verified=0,
            verification_token=token,
            created_at=now_ts(),
        )
        send_verification_email(email, name, token)
        return render_template("verify_sent.html", email=email)

    return render_template("register.html")


@auth_bp.route("/verify/<token>")
def verify(token):
    row = db.get("users", verification_token=token)
    if not row:
        return render_template("verify_result.html", success=False)

    db.update("users", filters={"id": row["id"]}, updates={"is_verified": 1, "verification_token": ""})
    return render_template("verify_result.html", success=True)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        row = db.get("users", email=email)
        if not row or not check_password_hash(row["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        if not row["is_verified"]:
            flash("Please verify your email before logging in. Check your inbox for the link.", "error")
            return render_template("login.html", email=email)

        login_user(User(row))
        return redirect(url_for("monitors.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
