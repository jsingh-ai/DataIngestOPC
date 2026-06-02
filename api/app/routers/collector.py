from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import CollectorCommand, CollectorConfigState
from app.schemas import CollectorActionResponse, CollectorCommandSummary, CollectorStatusResponse, PaginatedResponse
from app.services.command_service import enqueue_command

router = APIRouter(prefix="/api/collector", tags=["collector"])


@router.post("/reload-config", response_model=CollectorActionResponse)
def reload_config(db: Session = Depends(get_db), user: str = Depends(get_current_user)) -> CollectorActionResponse:
    command, state = enqueue_command(db, "reload_config", user, set_pending_reload=True)
    return CollectorActionResponse(
        command_id=command.command_id,
        command_type=command.command_type,
        status=command.status,
        active_config_version=state.active_config_version if state else None,
    )


@router.post("/restart", response_model=CollectorActionResponse)
def restart_collector(db: Session = Depends(get_db), user: str = Depends(get_current_user)) -> CollectorActionResponse:
    command, _ = enqueue_command(db, "restart_collector", user)
    return CollectorActionResponse(
        command_id=command.command_id,
        command_type=command.command_type,
        status=command.status,
    )


@router.get("/commands", response_model=PaginatedResponse)
def list_commands(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> PaginatedResponse:
    query = select(CollectorCommand).order_by(CollectorCommand.requested_at.desc())
    total = len(db.execute(query).scalars().all())
    items = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PaginatedResponse(
        items=[CollectorCommandSummary.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/status", response_model=CollectorStatusResponse)
def collector_status(db: Session = Depends(get_db), _: str = Depends(get_current_user)) -> CollectorStatusResponse:
    state = db.execute(select(CollectorConfigState).where(CollectorConfigState.id == 1)).scalar_one()
    commands = db.execute(
        select(CollectorCommand).order_by(CollectorCommand.requested_at.desc()).limit(20)
    ).scalars().all()
    return CollectorStatusResponse(
        active_config_version=state.active_config_version,
        pending_reload=state.pending_reload,
        recent_commands=[CollectorCommandSummary.model_validate(item) for item in commands],
    )
