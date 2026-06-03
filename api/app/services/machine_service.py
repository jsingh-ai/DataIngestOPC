from __future__ import annotations

import hashlib
from datetime import UTC, datetime
import re

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import ConfigAuditLog, Machine, MachineCollectionStatus, TagDefinition
from app.schemas import MachineCreate, MachineUpdate
from app.security import encrypt_secret


def _slugify_machine_code(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-")
    return slug.upper()


def resolve_machine_code(payload: MachineCreate) -> str:
    if payload.machine_code and payload.machine_code.strip():
        return payload.machine_code.strip()
    base_source = payload.display_name.strip() or payload.ip_address.strip() or "MACHINE"
    base = _slugify_machine_code(base_source) or "MACHINE"
    digest_input = f"{payload.display_name.strip()}|{payload.ip_address.strip()}|{payload.port}|{payload.opc_endpoint.strip()}"
    suffix = hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:6].upper()
    candidate = f"TMP-{base[:40]}-{suffix}"
    return candidate[:64]


def build_machine_from_payload(payload: MachineCreate) -> Machine:
    return Machine(
        machine_code=resolve_machine_code(payload),
        display_name=payload.display_name,
        ip_address=payload.ip_address,
        port=payload.port,
        opc_endpoint=payload.opc_endpoint,
        security_policy=None,
        security_mode=None,
        opc_username=payload.opc_username,
        opc_password_encrypted=encrypt_secret(payload.opc_password) if payload.opc_password else None,
        enabled=False,
        status="draft",
        notes=payload.notes,
    )


def build_machine_query(search: str | None) -> Select[tuple[Machine]]:
    query = select(Machine)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Machine.machine_code.like(pattern),
                Machine.display_name.like(pattern),
                Machine.ip_address.like(pattern),
                Machine.opc_endpoint.like(pattern),
            )
        )
    return query.order_by(Machine.machine_id.desc())


def create_machine(db: Session, payload: MachineCreate, changed_by: str, *, status: str = "draft") -> Machine:
    machine = build_machine_from_payload(payload)
    machine.status = status
    db.add(machine)
    db.flush()
    db.add(
        ConfigAuditLog(
            changed_by=changed_by,
            entity_type="machine",
            entity_id=str(machine.machine_id),
            action="create",
            new_value_json={"machine_code": machine.machine_code, "enabled": machine.enabled},
        )
    )
    db.commit()
    db.refresh(machine)
    return machine


def update_machine(db: Session, machine: Machine, payload: MachineUpdate, changed_by: str) -> Machine:
    old_values = {
        "display_name": machine.display_name,
        "ip_address": machine.ip_address,
        "port": machine.port,
        "opc_endpoint": machine.opc_endpoint,
        "enabled": machine.enabled,
        "status": machine.status,
    }
    updates = payload.model_dump(exclude_unset=True)
    password = updates.pop("opc_password", None)
    for key, value in updates.items():
        setattr(machine, key, value)
    if password:
        machine.opc_password_encrypted = encrypt_secret(password)
    machine.updated_at = datetime.now(UTC)
    db.add(
        ConfigAuditLog(
            changed_by=changed_by,
            entity_type="machine",
            entity_id=str(machine.machine_id),
            action="update",
            old_value_json=old_values,
            new_value_json=payload.model_dump(exclude_unset=True, exclude={"opc_password"}),
        )
    )
    db.commit()
    db.refresh(machine)
    return machine


def machine_tag_counts(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(TagDefinition.machine_id, func.count(TagDefinition.tag_id)).group_by(TagDefinition.machine_id)
    ).all()
    return {machine_id: count for machine_id, count in rows}


def machine_status_map(db: Session) -> dict[int, MachineCollectionStatus]:
    statuses = db.execute(select(MachineCollectionStatus)).scalars().all()
    return {row.machine_id: row for row in statuses}
