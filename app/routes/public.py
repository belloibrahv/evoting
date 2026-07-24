"""
Public routes — homepage and public results preview.
No authentication required.
"""
from flask import Blueprint, render_template
from app.models.election import Election, ElectionStatus

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    """Public homepage."""
    published = Election.query.filter_by(
        status=ElectionStatus.PUBLISHED
    ).order_by(Election.end_at.desc()).limit(3).all()
    return render_template("homepage/index.html", published_elections=published)


@public_bp.route("/about")
def about():
    return render_template("homepage/about.html")
