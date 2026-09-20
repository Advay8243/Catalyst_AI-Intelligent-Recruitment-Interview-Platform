import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.models import AuditEvent


def record_audit(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    event_type: str,
    description: str,
    application_id: uuid.UUID | None = None,
    actor: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        candidate_id=candidate_id,
        application_id=application_id,
        event_type=event_type,
        actor=actor,
        description=description,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event
