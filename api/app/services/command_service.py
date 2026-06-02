from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CollectorCommand, CollectorConfigState


def enqueue_command(
    db: Session,
    command_type: str,
    requested_by: str,
    command_payload: dict | None = None,
    set_pending_reload: bool = False,
) -> tuple[CollectorCommand, CollectorConfigState | None]:
    state = None
    if set_pending_reload:
        state = db.execute(select(CollectorConfigState).where(CollectorConfigState.id == 1)).scalar_one()
        state.active_config_version += 1
        state.pending_reload = True
        state.updated_by = requested_by
    command = CollectorCommand(
        command_type=command_type, requested_by=requested_by, command_payload=command_payload
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command, state
