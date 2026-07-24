"""
AuditService — centralised, append-only event logging.
Every mutating service calls log() so audit coverage can't be forgotten.
"""
import json
from typing import Optional
from flask import request
from app.extensions import db
from app.models.audit_log import AuditLog


class AuditService:
    @staticmethod
    def log(
        action: str,
        user_id: Optional[int] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """
        Write an audit record.
        `metadata` must never contain PII or plaintext vote content.
        """
        if ip_address is None:
            try:
                ip_address = request.remote_addr or "unknown"
            except RuntimeError:
                # Outside of request context (e.g., scheduler jobs)
                ip_address = "system"

        entry = AuditLog(
            user_id=user_id,
            action_performed=action,
            ip_address=ip_address,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.session.add(entry)
        # We do NOT commit here — the caller's transaction wraps everything.
        # This ensures the audit record and the mutating DB change are atomic.
        return entry
