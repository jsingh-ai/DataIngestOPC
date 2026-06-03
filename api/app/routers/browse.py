from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import TagBrowserCache, TagDefinition
from app.schemas import AddTagsFromCacheRequest, AddTagsFromCacheResponse, BrowseCacheSummary, PaginatedResponse
from app.services.tag_service import slugify_tag_key

router = APIRouter(tags=["browse"])


@router.get("/api/machines/{machine_id}/browse-cache", response_model=PaginatedResponse)
def list_browse_cache(
    machine_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
    search: str | None = None,
    folder_path: str | None = None,
    is_variable: bool | None = None,
    already_added: bool | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> PaginatedResponse:
    query = select(TagBrowserCache).where(TagBrowserCache.machine_id == machine_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                TagBrowserCache.browse_path.like(pattern),
                TagBrowserCache.display_name.like(pattern),
                TagBrowserCache.opc_node_id.like(pattern),
            )
        )
    if folder_path:
        query = query.where(TagBrowserCache.browse_path.like(f"{folder_path}%"))
    if is_variable is not None:
        query = query.where(TagBrowserCache.is_variable.is_(is_variable))
    if already_added is not None:
        query = query.where(TagBrowserCache.already_added.is_(already_added))
    query = query.order_by(TagBrowserCache.cache_id.asc())
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PaginatedResponse(
        items=[BrowseCacheSummary.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/api/machines/{machine_id}/add-tags-from-cache", response_model=AddTagsFromCacheResponse)
def add_tags_from_cache(
    machine_id: int,
    payload: AddTagsFromCacheRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> AddTagsFromCacheResponse:
    created_ids: list[int] = []
    skipped_ids: list[int] = []
    created_count = 0
    skipped_duplicates = 0
    for item in payload.tags:
        cache_row = db.get(TagBrowserCache, item.cache_id)
        if cache_row is None or cache_row.machine_id != machine_id:
            skipped_ids.append(item.cache_id)
            continue
        if not cache_row.is_variable:
            skipped_ids.append(item.cache_id)
            continue
        duplicate = db.execute(
            select(TagDefinition).where(
                TagDefinition.machine_id == machine_id, TagDefinition.opc_node_id == cache_row.opc_node_id
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            skipped_duplicates += 1
            skipped_ids.append(item.cache_id)
            cache_row.already_added = True
            continue
        display_name = item.display_name or cache_row.display_name or cache_row.browse_name or "Tag"
        source_key = item.tag_key or cache_row.browse_path or display_name
        base_tag_key = slugify_tag_key(source_key)
        tag_key = base_tag_key
        suffix = 1
        while db.execute(
            select(TagDefinition.tag_id).where(
                TagDefinition.machine_id == machine_id,
                TagDefinition.tag_key == tag_key,
            )
        ).scalar_one_or_none() is not None:
            suffix += 1
            tag_key = f"{base_tag_key}_{suffix}"
        tag = TagDefinition(
            machine_id=machine_id,
            tag_key=tag_key,
            display_name=display_name[:128],
            opc_node_id=cache_row.opc_node_id,
            browse_path=cache_row.browse_path,
            folder_path=item.folder_path or cache_row.browse_path.rsplit("/", 1)[0] if cache_row.browse_path else None,
            data_type=cache_row.data_type,
            engineering_unit=item.engineering_unit,
            scan_profile_id=item.scan_profile_id,
            enabled=item.enabled,
        )
        db.add(tag)
        db.flush()
        cache_row.already_added = True
        created_ids.append(tag.tag_id)
        created_count += 1
    db.commit()
    return AddTagsFromCacheResponse(
        created_count=created_count,
        skipped_duplicates=skipped_duplicates,
        created_tag_ids=created_ids,
        skipped_cache_ids=skipped_ids,
    )


@router.delete("/api/machines/{machine_id}/browse-cache")
def clear_browse_cache(machine_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)) -> dict:
    result = db.execute(delete(TagBrowserCache).where(TagBrowserCache.machine_id == machine_id))
    db.commit()
    return {"deleted": int(getattr(result, "rowcount", 0) or 0)}
