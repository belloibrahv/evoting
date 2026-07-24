"""
Custom route decorators for RBAC enforcement.
Usage:
    @admin_required
    def my_admin_view(): ...
"""
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user, login_required


def admin_required(f):
    """Require the logged-in user to have the 'admin' role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def voter_required(f):
    """Require the logged-in user to have the 'voter' role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_voter:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def auditor_or_admin_required(f):
    """Allow admins and auditors (results viewers)."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ("admin", "auditor"):
            abort(403)
        return f(*args, **kwargs)
    return decorated
