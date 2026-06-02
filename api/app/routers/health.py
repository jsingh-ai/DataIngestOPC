from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Machine, MachineCollectionStatus, TagCurrentValue, TagDefinition
from app.schemas import MachineHealthSummary, PaginatedResponse, TagCurrentValueResponse

router = APIRouter(tags=["health"])


@router.get("/api/health/machines", response_model=PaginatedResponse)
def list_machine_health(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> PaginatedResponse:
    query = select(Machine).order_by(Machine.machine_id.asc())
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Machine.machine_code.like(pattern), Machine.display_name.like(pattern)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    machines = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    status_map = {
        row.machine_id: row for row in db.execute(select(MachineCollectionStatus)).scalars().all()
    }
    items = []
    for machine in machines:
        status_row = status_map.get(machine.machine_id)
        items.append(
            MachineHealthSummary.model_validate(
                {
                    "machine_id": machine.machine_id,
                    "machine_code": machine.machine_code,
                    "display_name": machine.display_name,
                    "enabled": machine.enabled,
                    "status": machine.status,
                    "collector_status": status_row.status if status_row else None,
                    "opc_connected": status_row.opc_connected if status_row else None,
                    "mysql_connected": status_row.mysql_connected if status_row else None,
                    "last_heartbeat_ts_utc": status_row.last_heartbeat_ts_utc if status_row else None,
                    "expected_tag_count": status_row.expected_tag_count if status_row else 0,
                    "successful_tag_count": status_row.successful_tag_count if status_row else 0,
                    "failed_tag_count": status_row.failed_tag_count if status_row else 0,
                    "collection_duration_ms": status_row.collection_duration_ms if status_row else None,
                    "local_buffer_rows": status_row.local_buffer_rows if status_row else 0,
                    "last_error_message": status_row.last_error_message if status_row else None,
                }
            )
        )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/api/machines/{machine_id}/status", response_model=MachineHealthSummary)
def machine_status(machine_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)) -> MachineHealthSummary:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    status_row = db.get(MachineCollectionStatus, machine_id)
    return MachineHealthSummary.model_validate(
        {
            "machine_id": machine.machine_id,
            "machine_code": machine.machine_code,
            "display_name": machine.display_name,
            "enabled": machine.enabled,
            "status": machine.status,
            "collector_status": status_row.status if status_row else None,
            "opc_connected": status_row.opc_connected if status_row else None,
            "mysql_connected": status_row.mysql_connected if status_row else None,
            "last_heartbeat_ts_utc": status_row.last_heartbeat_ts_utc if status_row else None,
            "expected_tag_count": status_row.expected_tag_count if status_row else 0,
            "successful_tag_count": status_row.successful_tag_count if status_row else 0,
            "failed_tag_count": status_row.failed_tag_count if status_row else 0,
            "collection_duration_ms": status_row.collection_duration_ms if status_row else None,
            "local_buffer_rows": status_row.local_buffer_rows if status_row else 0,
            "last_error_message": status_row.last_error_message if status_row else None,
        }
    )


@router.get("/api/machines/{machine_id}/current-values", response_model=PaginatedResponse)
def current_values(
    machine_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> PaginatedResponse:
    query = (
        select(TagCurrentValue)
        .join(TagDefinition, TagDefinition.tag_id == TagCurrentValue.tag_id)
        .where(TagCurrentValue.machine_id == machine_id)
    )
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(TagDefinition.tag_key.like(pattern), TagDefinition.display_name.like(pattern)))
    query = query.order_by(TagCurrentValue.sample_ts_utc.desc())
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PaginatedResponse(
        items=[TagCurrentValueResponse.model_validate(item, from_attributes=True) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/api/tags/{tag_id}/current-value", response_model=TagCurrentValueResponse)
def current_value_by_tag(tag_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)) -> TagCurrentValueResponse:
    row = db.execute(select(TagCurrentValue).where(TagCurrentValue.tag_id == tag_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Current value not found")
    return TagCurrentValueResponse.model_validate(row, from_attributes=True)
