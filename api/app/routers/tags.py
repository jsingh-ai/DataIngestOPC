from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import ScanProfile, TagDefinition
from app.schemas import (
    BulkTagIds,
    BulkTagScanProfileUpdate,
    PaginatedResponse,
    ScanProfileSummary,
    TagCreate,
    TagSummary,
    TagUpdate,
)
from app.services.tag_service import (
    apply_bulk_enabled,
    apply_bulk_scan_profile,
    build_tag_query,
    collection_status_map,
    create_tag,
    current_value_map,
    update_tag,
)

router = APIRouter(tags=["tags"])


@router.get("/api/scan-profiles", response_model=list[ScanProfileSummary])
def list_scan_profiles(db: Session = Depends(get_db), _: str = Depends(get_current_user)) -> list[ScanProfileSummary]:
    rows = db.execute(select(ScanProfile).where(ScanProfile.enabled.is_(True)).order_by(ScanProfile.scan_profile_id.asc())).scalars().all()
    return [ScanProfileSummary.model_validate(row) for row in rows]


@router.get("/api/machines/{machine_id}/tags", response_model=PaginatedResponse)
def list_tags(
    machine_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
    search: str | None = None,
    enabled: bool | None = None,
    folder_path: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> PaginatedResponse:
    query = build_tag_query(machine_id, search, enabled, folder_path)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    tags = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    tag_ids = [tag.tag_id for tag in tags]
    current_map = current_value_map(db, machine_id, tag_ids)
    status_map = collection_status_map(db, machine_id, tag_ids)
    items = []
    for tag in tags:
        current = current_map.get(tag.tag_id)
        tag_status = status_map.get(tag.tag_id)
        last_value = None
        if current:
            last_value = (
                str(current.value_num)
                if current.value_num is not None
                else str(current.value_bool)
                if current.value_bool is not None
                else current.value_str
            )
        items.append(
            TagSummary.model_validate(
                {
                    **tag.__dict__,
                    "last_value": last_value,
                    "last_quality": current.quality_code if current else None,
                    "last_seen": current.sample_ts_utc if current else None,
                    "status": tag_status.status if tag_status else "unknown",
                }
            )
        )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/api/machines/{machine_id}/tags", response_model=TagSummary, status_code=status.HTTP_201_CREATED)
def create_tag_route(
    machine_id: int,
    payload: TagCreate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> TagSummary:
    tag = create_tag(db, machine_id, payload, user)
    return TagSummary.model_validate({**tag.__dict__, "status": "unknown"})


@router.patch("/api/tags/{tag_id}", response_model=TagSummary)
def patch_tag(
    tag_id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> TagSummary:
    tag = db.get(TagDefinition, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    updated = update_tag(db, tag, payload, user)
    return TagSummary.model_validate({**updated.__dict__, "status": "unknown"})


@router.post("/api/tags/bulk-enable")
def bulk_enable(payload: BulkTagIds, db: Session = Depends(get_db), user: str = Depends(get_current_user)) -> dict:
    updated = apply_bulk_enabled(db, payload.tag_ids, True, user)
    return {"updated": updated}


@router.post("/api/tags/bulk-disable")
def bulk_disable(payload: BulkTagIds, db: Session = Depends(get_db), user: str = Depends(get_current_user)) -> dict:
    updated = apply_bulk_enabled(db, payload.tag_ids, False, user)
    return {"updated": updated}


@router.post("/api/tags/bulk-update-scan-profile")
def bulk_update_scan_profile(
    payload: BulkTagScanProfileUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> dict:
    updated = apply_bulk_scan_profile(db, payload.tag_ids, payload.scan_profile_id, user)
    return {"updated": updated}
