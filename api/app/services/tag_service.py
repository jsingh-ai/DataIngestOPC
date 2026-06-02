from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from app.models import ConfigAuditLog, TagCollectionStatus, TagCurrentValue, TagDefinition
from app.schemas import TagCreate, TagUpdate


def slugify_tag_key(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return cleaned[:128] or "tag"


def build_tag_query(
    machine_id: int,
    search: str | None,
    enabled: bool | None,
    folder_path: str | None,
) -> Select[tuple[TagDefinition]]:
    query = select(TagDefinition).where(TagDefinition.machine_id == machine_id, TagDefinition.archived.is_(False))
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                TagDefinition.tag_key.like(pattern),
                TagDefinition.display_name.like(pattern),
                TagDefinition.opc_node_id.like(pattern),
                TagDefinition.browse_path.like(pattern),
            )
        )
    if enabled is not None:
        query = query.where(TagDefinition.enabled.is_(enabled))
    if folder_path:
        query = query.where(TagDefinition.folder_path.like(f"{folder_path}%"))
    return query.order_by(TagDefinition.tag_id.asc())


def create_tag(db: Session, machine_id: int, payload: TagCreate, changed_by: str) -> TagDefinition:
    tag = TagDefinition(machine_id=machine_id, **payload.model_dump())
    db.add(tag)
    db.flush()
    db.add(
        ConfigAuditLog(
            changed_by=changed_by,
            entity_type="tag_definition",
            entity_id=str(tag.tag_id),
            action="create",
            new_value_json={"machine_id": machine_id, "tag_key": tag.tag_key},
        )
    )
    db.commit()
    db.refresh(tag)
    return tag


def update_tag(db: Session, tag: TagDefinition, payload: TagUpdate, changed_by: str) -> TagDefinition:
    old_values = {
        "display_name": tag.display_name,
        "folder_path": tag.folder_path,
        "scan_profile_id": tag.scan_profile_id,
        "enabled": tag.enabled,
    }
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tag, key, value)
    tag.updated_at = datetime.now(UTC)
    db.add(
        ConfigAuditLog(
            changed_by=changed_by,
            entity_type="tag_definition",
            entity_id=str(tag.tag_id),
            action="update",
            old_value_json=old_values,
            new_value_json=payload.model_dump(exclude_unset=True),
        )
    )
    db.commit()
    db.refresh(tag)
    return tag


def apply_bulk_enabled(db: Session, tag_ids: list[int], enabled: bool, changed_by: str) -> int:
    tags = db.execute(select(TagDefinition).where(TagDefinition.tag_id.in_(tag_ids))).scalars().all()
    now = datetime.now(UTC)
    for tag in tags:
        tag.enabled = enabled
        tag.updated_at = now
    db.add(
        ConfigAuditLog(
            changed_by=changed_by,
            entity_type="tag_definition",
            entity_id="bulk",
            action="bulk_enable" if enabled else "bulk_disable",
            new_value_json={"tag_ids": tag_ids},
        )
    )
    db.commit()
    return len(tags)


def apply_bulk_scan_profile(db: Session, tag_ids: list[int], scan_profile_id: int | None, changed_by: str) -> int:
    tags = db.execute(select(TagDefinition).where(TagDefinition.tag_id.in_(tag_ids))).scalars().all()
    now = datetime.now(UTC)
    for tag in tags:
        tag.scan_profile_id = scan_profile_id
        tag.updated_at = now
    db.add(
        ConfigAuditLog(
            changed_by=changed_by,
            entity_type="tag_definition",
            entity_id="bulk",
            action="bulk_update_scan_profile",
            new_value_json={"tag_ids": tag_ids, "scan_profile_id": scan_profile_id},
        )
    )
    db.commit()
    return len(tags)


def current_value_map(db: Session, machine_id: int, tag_ids: list[int]) -> dict[int, TagCurrentValue]:
    if not tag_ids:
        return {}
    rows = db.execute(
        select(TagCurrentValue).where(
            and_(TagCurrentValue.machine_id == machine_id, TagCurrentValue.tag_id.in_(tag_ids))
        )
    ).scalars()
    return {row.tag_id: row for row in rows}


def collection_status_map(db: Session, machine_id: int, tag_ids: list[int]) -> dict[int, TagCollectionStatus]:
    if not tag_ids:
        return {}
    rows = db.execute(
        select(TagCollectionStatus).where(
            and_(TagCollectionStatus.machine_id == machine_id, TagCollectionStatus.tag_id.in_(tag_ids))
        )
    ).scalars()
    return {row.tag_id: row for row in rows}
