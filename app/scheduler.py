"""
Background scheduler — auto-transitions elections between SCHEDULED → OPEN
and OPEN → CLOSED at configured timestamps.

Initialised in the app factory when not running tests.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler: BackgroundScheduler | None = None


def init_scheduler(app) -> None:
    """Attach the scheduler to the Flask app and start it."""
    global _scheduler

    if _scheduler and _scheduler.running:
        return  # Already running (e.g., reloader fork)

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=lambda: _check_transitions(app),
        trigger=IntervalTrigger(minutes=1),
        id="election_transition_check",
        replace_existing=True,
    )
    _scheduler.start()
    app.logger.info("Election scheduler started.")


def _check_transitions(app) -> None:
    """
    Run inside the app context.
    Checks all elections that should be auto-opened or auto-closed.
    """
    from datetime import datetime, timezone
    with app.app_context():
        from app.extensions import db
        from app.models.election import Election, ElectionStatus
        from app.services.audit_service import AuditService

        now = datetime.now(timezone.utc)

        # SCHEDULED → OPEN (past start_at)
        to_open = Election.query.filter(
            Election.status == ElectionStatus.SCHEDULED,
            Election.start_at <= now,
        ).all()
        for election in to_open:
            election.status = ElectionStatus.OPEN
            AuditService.log(
                action="ELECTION_TRANSITIONED",
                metadata={
                    "election_id": election.election_id,
                    "from": ElectionStatus.SCHEDULED,
                    "to": ElectionStatus.OPEN,
                    "trigger": "scheduler",
                },
                ip_address="system",
            )

        # OPEN → CLOSED (past end_at)
        to_close = Election.query.filter(
            Election.status == ElectionStatus.OPEN,
            Election.end_at <= now,
        ).all()
        for election in to_close:
            election.status = ElectionStatus.CLOSED
            AuditService.log(
                action="ELECTION_TRANSITIONED",
                metadata={
                    "election_id": election.election_id,
                    "from": ElectionStatus.OPEN,
                    "to": ElectionStatus.CLOSED,
                    "trigger": "scheduler",
                },
                ip_address="system",
            )

        if to_open or to_close:
            db.session.commit()
