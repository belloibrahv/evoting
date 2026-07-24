"""
Voter routes — dashboard, ballot, receipt.
"""
import json
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, abort
)
from flask_login import login_required, current_user
from app.models.election import Election, ElectionStatus
from app.models.eligible_voter import EligibleVoter
from app.models.ballot import Ballot
from app.services.ballot_service import BallotService, BallotError
from app.utils.decorators import voter_required
from app.extensions import limiter

voter_bp = Blueprint("voter", __name__)


@voter_bp.route("/")
@voter_required
def dashboard():
    """Voter home — shows open elections they're eligible for."""
    open_elections = Election.query.filter_by(status=ElectionStatus.OPEN).all()
    eligible = []
    for election in open_elections:
        roster = EligibleVoter.query.filter_by(
            election_id=election.election_id,
            matric_number=current_user.matric_number,
        ).first()
        if roster:
            eligible.append({
                "election": election,
                "has_voted": roster.has_voted,
            })
    return render_template("voter/dashboard.html", eligible=eligible)


@voter_bp.route("/ballot/<int:election_id>")
@voter_required
def ballot(election_id: int):
    """Show the ballot form for a specific election."""
    election = Election.query.get_or_404(election_id)

    if election.status != ElectionStatus.OPEN:
        flash("This election is not currently open for voting.", "warning")
        return redirect(url_for("voter.dashboard"))

    roster = EligibleVoter.query.filter_by(
        election_id=election_id,
        matric_number=current_user.matric_number,
    ).first()
    if not roster:
        flash("You are not eligible to vote in this election.", "warning")
        return redirect(url_for("voter.dashboard"))

    if roster.has_voted:
        flash("You have already cast your vote in this election.", "info")
        return redirect(url_for("voter.dashboard"))

    return render_template("voter/ballot.html", election=election)


@voter_bp.route("/ballot/<int:election_id>/submit", methods=["POST"])
@voter_required
@limiter.limit("5 per hour")
def submit_ballot(election_id: int):
    """Accept and encrypt a ballot submission."""
    election = Election.query.get_or_404(election_id)

    try:
        raw_selections = request.get_json(silent=True) or {}
        # Convert to {position_id: candidate_id}
        selections = {
            str(k): int(v) for k, v in raw_selections.items()
        }
        if not selections:
            return jsonify({"error": "No selections provided."}), 400

        ballot = BallotService.cast_vote(
            user_id=current_user.user_id,
            election=election,
            selections=selections,
            ip_address=request.remote_addr,
        )
        return jsonify({
            "success": True,
            "receipt_id": ballot.receipt_id,
            "submitted_at": ballot.submitted_at.isoformat(),
            "ballot_hash": ballot.ballot_hash_sha256,
        })
    except BallotError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "An unexpected error occurred."}), 500


@voter_bp.route("/receipt/<receipt_id>")
@login_required
def receipt(receipt_id: str):
    """Show a vote receipt (metadata only — never reveals vote content)."""
    ballot_entry = Ballot.query.filter_by(receipt_id=receipt_id).first_or_404()
    # A voter can only view their own receipt.
    # We verify ownership via anonymised_voter_ref.
    from app.services.crypto_service import CryptoService
    from flask import current_app
    salt = current_app.config.get("SECRET_KEY", "")
    expected_ref = CryptoService.anonymise_voter(
        current_user.user_id, ballot_entry.election_id, salt
    )
    if not current_user.is_admin and ballot_entry.anonymised_voter_ref != expected_ref:
        abort(403)

    return render_template(
        "voter/receipt.html",
        ballot=ballot_entry,
        election=ballot_entry.election,
    )
