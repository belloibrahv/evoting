"""
Admin routes — election management, candidate CRUD, voter import, tally,
audit log, turnout stats.
"""
import json
import csv
import io
from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, Response, current_app
)
from flask_login import current_user
from app.models.election import Election, ElectionStatus
from app.models.position import Position
from app.models.candidate import Candidate
from app.models.audit_log import AuditLog
from app.services.election_service import ElectionService, ElectionError
from app.services.tally_service import TallyService
from app.services.audit_service import AuditService
from app.utils.decorators import admin_required
from app.utils.helpers import save_upload, allowed_image
from app.extensions import db

admin_bp = Blueprint("admin", __name__)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@admin_required
def dashboard():
    elections = Election.query.order_by(Election.created_at.desc()).all()
    return render_template("admin/dashboard.html", elections=elections)


# ── Elections CRUD ────────────────────────────────────────────────────────────

@admin_bp.route("/elections/new", methods=["GET", "POST"])
@admin_required
def create_election():
    if request.method == "POST":
        try:
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            start_at = datetime.fromisoformat(request.form.get("start_at", ""))
            end_at = datetime.fromisoformat(request.form.get("end_at", ""))
            positions_raw = request.form.get("positions", "").strip()
            positions = [p.strip() for p in positions_raw.split("\n") if p.strip()]

            if not title:
                raise ElectionError("Election title is required.")
            if not positions:
                raise ElectionError("At least one position is required.")

            election, private_pem = ElectionService.create_election(
                title=title,
                description=description,
                start_at=start_at,
                end_at=end_at,
                created_by=current_user.user_id,
                positions=positions,
                ip_address=request.remote_addr,
            )
            # Present the private key ONCE for the admin to download
            flash(
                "Election created. Download the private key below — it will not be shown again.",
                "success",
            )
            return render_template(
                "admin/key_export.html",
                election=election,
                private_pem=private_pem,
            )
        except (ElectionError, ValueError) as e:
            flash(str(e), "error")

    return render_template("admin/election_form.html", election=None)


@admin_bp.route("/elections/<int:election_id>")
@admin_required
def election_detail(election_id: int):
    election = Election.query.get_or_404(election_id)
    return render_template("admin/election_detail.html", election=election)


@admin_bp.route("/elections/<int:election_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_election(election_id: int):
    election = Election.query.get_or_404(election_id)
    if not election.is_editable:
        flash("Only DRAFT elections can be edited.", "warning")
        return redirect(url_for("admin.election_detail", election_id=election_id))

    if request.method == "POST":
        try:
            start_at = datetime.fromisoformat(request.form.get("start_at", ""))
            end_at = datetime.fromisoformat(request.form.get("end_at", ""))
            ElectionService.update_election(
                election=election,
                title=request.form.get("title"),
                description=request.form.get("description"),
                start_at=start_at,
                end_at=end_at,
                user_id=current_user.user_id,
                ip_address=request.remote_addr,
            )
            flash("Election updated.", "success")
            return redirect(url_for("admin.election_detail", election_id=election_id))
        except ElectionError as e:
            flash(str(e), "error")

    return render_template("admin/election_form.html", election=election)


@admin_bp.route("/elections/<int:election_id>/transition", methods=["POST"])
@admin_required
def transition_election(election_id: int):
    election = Election.query.get_or_404(election_id)
    to_status = request.form.get("to_status", "").strip()
    try:
        ElectionService.transition(
            election, to_status,
            user_id=current_user.user_id,
            ip_address=request.remote_addr,
        )
        flash(f"Election moved to {to_status.upper()}.", "success")
    except ElectionError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.election_detail", election_id=election_id))


# ── Candidate Management ──────────────────────────────────────────────────────

@admin_bp.route("/elections/<int:election_id>/candidates/add", methods=["GET", "POST"])
@admin_required
def add_candidate(election_id: int):
    election = Election.query.get_or_404(election_id)
    if not election.is_editable:
        flash("Candidates can only be added in DRAFT status.", "warning")
        return redirect(url_for("admin.election_detail", election_id=election_id))

    if request.method == "POST":
        try:
            position_id = int(request.form.get("position_id", 0))
            position = Position.query.get_or_404(position_id)

            photo_url = None
            if "photo" in request.files:
                photo_file = request.files["photo"]
                if photo_file and photo_file.filename and allowed_image(photo_file.filename):
                    photo_url = save_upload(photo_file, "candidates")

            ElectionService.add_candidate(
                position=position,
                full_name=request.form.get("full_name", ""),
                matric_number=request.form.get("matric_number") or None,
                photo_url=photo_url,
                manifesto=request.form.get("manifesto") or None,
            )
            flash("Candidate added.", "success")
            return redirect(url_for("admin.election_detail", election_id=election_id))
        except ElectionError as e:
            flash(str(e), "error")

    return render_template(
        "admin/candidate_form.html", election=election, candidate=None
    )


@admin_bp.route("/candidates/<int:candidate_id>/delete", methods=["POST"])
@admin_required
def delete_candidate(candidate_id: int):
    candidate = Candidate.query.get_or_404(candidate_id)
    election_id = candidate.position.election_id
    try:
        ElectionService.remove_candidate(candidate)
        flash("Candidate removed.", "success")
    except ElectionError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.election_detail", election_id=election_id))


# ── Voter Roster Import ───────────────────────────────────────────────────────

@admin_bp.route("/elections/<int:election_id>/voters/import", methods=["GET", "POST"])
@admin_required
def import_voters(election_id: int):
    election = Election.query.get_or_404(election_id)

    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or not file.filename.endswith(".csv"):
            flash("Please upload a .csv file.", "error")
            return redirect(request.url)

        csv_content = file.read().decode("utf-8", errors="replace")
        result = ElectionService.import_voters_csv(
            election=election,
            csv_content=csv_content,
            user_id=current_user.user_id,
            ip_address=request.remote_addr,
        )
        flash(
            f"Import complete: {result['added']} added, {result['skipped']} skipped.",
            "success" if not result["errors"] else "warning",
        )
        if result["errors"]:
            for err in result["errors"][:10]:
                flash(err, "warning")
        return redirect(url_for("admin.election_detail", election_id=election_id))

    return render_template("admin/import_voters.html", election=election)


# ── Tally ─────────────────────────────────────────────────────────────────────

@admin_bp.route("/elections/<int:election_id>/tally", methods=["GET", "POST"])
@admin_required
def tally(election_id: int):
    election = Election.query.get_or_404(election_id)

    if request.method == "POST":
        private_pem = request.form.get("private_pem", "").strip()
        passphrase = request.form.get("passphrase", "").strip()

        if not private_pem:
            # Try reading from keys/ folder (dev convenience)
            key_path = f"{current_app.config.get('KEYS_FOLDER', 'keys')}/election_{election_id}_private.pem"
            try:
                with open(key_path) as f:
                    private_pem = f.read()
            except FileNotFoundError:
                flash("Private key not found. Please paste it manually.", "error")
                return render_template("admin/tally.html", election=election)

        try:
            results = TallyService.run_tally(
                election=election,
                private_pem=private_pem,
                passphrase=passphrase,
                user_id=current_user.user_id,
                ip_address=request.remote_addr,
            )
            return render_template(
                "admin/tally_results.html", election=election, results=results
            )
        except Exception as e:
            flash(f"Tally failed: {e}", "error")

    return render_template("admin/tally.html", election=election)


@admin_bp.route("/elections/<int:election_id>/publish", methods=["POST"])
@admin_required
def publish_results(election_id: int):
    election = Election.query.get_or_404(election_id)
    try:
        ElectionService.transition(
            election,
            ElectionStatus.PUBLISHED,
            user_id=current_user.user_id,
            ip_address=request.remote_addr,
        )
        AuditService.log(
            action="RESULTS_PUBLISHED",
            user_id=current_user.user_id,
            metadata={"election_id": election_id},
            ip_address=request.remote_addr,
        )
        db.session.commit()
        flash("Results published successfully.", "success")
    except ElectionError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.election_detail", election_id=election_id))


# ── Turnout Stats (AJAX) ──────────────────────────────────────────────────────

@admin_bp.route("/elections/<int:election_id>/turnout")
@admin_required
def turnout_stats(election_id: int):
    election = Election.query.get_or_404(election_id)
    return jsonify({
        "registered": election.voter_count,
        "voted": election.voted_count,
        "turnout_pct": election.turnout_pct,
    })


# ── Audit Log ─────────────────────────────────────────────────────────────────

@admin_bp.route("/audit")
@admin_required
def audit_log():
    page = request.args.get("page", 1, type=int)
    action = request.args.get("action", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query = AuditLog.query.order_by(AuditLog.timestamp.desc())

    if action:
        query = query.filter(AuditLog.action_performed.ilike(f"%{action}%"))
    if date_from:
        try:
            query = query.filter(
                AuditLog.timestamp >= datetime.fromisoformat(date_from)
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                AuditLog.timestamp <= datetime.fromisoformat(date_to)
            )
        except ValueError:
            pass

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    return render_template(
        "admin/audit_log.html",
        pagination=pagination,
        filters={"action": action, "date_from": date_from, "date_to": date_to},
    )


@admin_bp.route("/audit/export")
@admin_required
def export_audit_csv():
    entries = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10000).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["log_id", "user_id", "action", "ip_address", "metadata", "timestamp"])
    for e in entries:
        writer.writerow([
            e.log_id, e.user_id, e.action_performed,
            e.ip_address, e.metadata_json or "", e.timestamp.isoformat()
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=audit_log.csv"},
    )
