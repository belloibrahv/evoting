"""
REST API routes — JSON endpoints for AJAX / external integrations.
Mirrors the contract in §8 of the spec.
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models.election import Election, ElectionStatus
from app.models.eligible_voter import EligibleVoter
from app.utils.decorators import admin_required

api_bp = Blueprint("api", __name__)


@api_bp.route("/elections")
def list_elections():
    """Public: list elections with title and status only."""
    elections = Election.query.order_by(Election.created_at.desc()).all()
    return jsonify([
        {
            "election_id": e.election_id,
            "title": e.title,
            "status": e.status,
            "start_at": e.start_at.isoformat(),
            "end_at": e.end_at.isoformat(),
        }
        for e in elections
    ])


@api_bp.route("/elections/<int:election_id>/results")
def election_results(election_id: int):
    """Public: published results only."""
    election = Election.query.get_or_404(election_id)
    if election.status != ElectionStatus.PUBLISHED:
        return jsonify({"error": "Results not published yet."}), 404

    data = {}
    for position in election.positions:
        total = sum(
            0 for _ in []  # tallied from DB in production; here as stub
        )
        data[position.position_id] = {
            "title": position.title,
            "candidates": [
                {
                    "candidate_id": c.candidate_id,
                    "name": c.full_name,
                    "photo_url": c.photo_url,
                }
                for c in position.candidates
            ],
        }
    return jsonify(data)


@api_bp.route("/elections/<int:election_id>/status")
@login_required
def voter_status(election_id: int):
    """Voter: has this voter already voted?"""
    roster = EligibleVoter.query.filter_by(
        election_id=election_id,
        matric_number=current_user.matric_number,
    ).first()
    if not roster:
        return jsonify({"eligible": False, "has_voted": False})
    return jsonify({"eligible": True, "has_voted": roster.has_voted})


@api_bp.route("/elections/<int:election_id>/turnout")
@admin_required
def turnout(election_id: int):
    election = Election.query.get_or_404(election_id)
    return jsonify({
        "registered": election.voter_count,
        "voted": election.voted_count,
        "turnout_pct": election.turnout_pct,
    })
