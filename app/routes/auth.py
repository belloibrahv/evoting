"""
Auth routes — register, login, logout, password reset.
"""
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, session
)
from flask_login import current_user, login_required
from app.services.auth_service import AuthService, AuthError
from app.extensions import limiter

auth_bp = Blueprint("auth", __name__)


# ── Registration ──────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(_dashboard_url())

    if request.method == "POST":
        matric = request.form.get("matric_number", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip() or None

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/register.html", form_data=request.form)

        try:
            AuthService.register_voter(
                matric_number=matric,
                password=password,
                full_name=full_name,
                email=email,
                ip_address=request.remote_addr,
            )
            flash(
                "Account created successfully. You can now log in.",
                "success",
            )
            return redirect(url_for("auth.login"))
        except AuthError as e:
            flash(str(e), "error")
            return render_template("auth/register.html", form_data=request.form)

    return render_template("auth/register.html", form_data={})


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(_dashboard_url())

    if request.method == "POST":
        matric = request.form.get("matric_number", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        try:
            user = AuthService.authenticate(
                matric_number=matric,
                password=password,
                remember=remember,
                ip_address=request.remote_addr,
            )
            # Mark session as permanent so idle timeout applies
            session.permanent = True
            return redirect(_dashboard_url())
        except AuthError as e:
            flash(str(e), "error")
            return render_template(
                "auth/login.html", form_data={"matric_number": matric}
            )

    return render_template("auth/login.html", form_data={})


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    AuthService.logout(
        user_id=current_user.user_id,
        ip_address=request.remote_addr,
    )
    flash("You have been logged out.", "info")
    return redirect(url_for("public.index"))


# ── Password Reset ────────────────────────────────────────────────────────────

@auth_bp.route("/password-reset", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def password_reset_request():
    if request.method == "POST":
        matric = request.form.get("matric_number", "").strip()
        raw_token = AuthService.request_password_reset(
            matric_number=matric,
            ip_address=request.remote_addr,
        )
        # Always show the same message to prevent enumeration
        flash(
            "If your matriculation number is registered, a reset link has been issued. "
            "Contact the Electoral Commission if you need assistance.",
            "info",
        )
        # In dev: show the raw token in flash for convenience
        if raw_token:
            flash(
                f"[DEV] Reset token: {raw_token} — use at /auth/password-reset/<token>",
                "warning",
            )
        return redirect(url_for("auth.login"))

    return render_template("auth/password_reset_request.html")


@auth_bp.route("/password-reset/<token>", methods=["GET", "POST"])
def password_reset_confirm(token: str):
    if request.method == "POST":
        new_password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if new_password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/password_reset_confirm.html", token=token)

        success = AuthService.complete_password_reset(
            raw_token=token,
            new_password=new_password,
            ip_address=request.remote_addr,
        )
        if success:
            flash("Password updated successfully. Please log in.", "success")
            return redirect(url_for("auth.login"))
        else:
            flash("This reset link is invalid or has expired.", "error")
            return redirect(url_for("auth.password_reset_request"))

    return render_template("auth/password_reset_confirm.html", token=token)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dashboard_url() -> str:
    from flask_login import current_user
    if current_user.is_admin:
        return url_for("admin.dashboard")
    return url_for("voter.dashboard")
