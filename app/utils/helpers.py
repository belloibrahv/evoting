"""
Miscellaneous helper utilities used across routes and services.
"""
import os
import uuid
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from flask import current_app


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_image(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def save_upload(file_storage, subfolder: str = "uploads") -> str:
    """
    Save an uploaded file to static/uploads/<subfolder>/.
    Returns the relative URL path (e.g. 'uploads/photos/abc123.jpg').
    """
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else "jpg"
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    upload_dir = os.path.join(
        current_app.config["UPLOAD_FOLDER"], subfolder
    )
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, unique_name))
    return f"uploads/{subfolder}/{unique_name}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def format_datetime(dt: datetime) -> str:
    """Human-friendly UTC datetime string."""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%d %b %Y, %H:%M UTC")
