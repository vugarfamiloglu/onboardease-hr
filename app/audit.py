"""Audit trail + system log helpers."""
import json

from flask import request
from flask_login import current_user

from .extensions import db
from .models import AuditLog, SystemLog


def audit(action, entity_type, entity_id=None, summary=""):
    """Record a who-did-what entry (viewed/edited/downloaded/approved/…)."""
    db.session.add(AuditLog(
        actor_id=getattr(current_user, "id", None),
        actor_name=getattr(current_user, "name", "system"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        ip=request.remote_addr if request else None,
    ))
    db.session.commit()


def syslog(level, source, message, meta=None):
    """Record an application/system event for the in-app log monitor."""
    db.session.add(SystemLog(
        level=level, source=source, message=message,
        meta=json.dumps(meta) if meta else None,
    ))
    db.session.commit()
