"""
Results routes — public read-only view of published results.
"""
from flask import Blueprint, render_template, abort
from app.models.election import Election, ElectionStatus

results_bp = Blueprint("results", __name__)


@results_bp.route("/")
def index():
    published = Election.query.filter_by(
        status=ElectionStatus.PUBLISHED
    ).order_by(Election.end_at.desc()).all()
    return render_template("results/index.html", elections=published)


@results_bp.route("/<int:election_id>")
def election_results(election_id: int):
    election = Election.query.get_or_404(election_id)
    if election.status != ElectionStatus.PUBLISHED:
        abort(404)  # Results not published yet — don't reveal existence
    return render_template("results/election.html", election=election)
