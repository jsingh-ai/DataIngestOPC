from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import ConfigAuditLog, Machine, MachineCollectionStatus, TagDefinition
from app.schemas import MachineCreate, MachineUpdate
from app.security import encrypt_secret


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


def create_machine(db: Session, payload: MachineCreate, changed_by: str) -> Machine:
    machine = Machine(
        machine_code=payload.machine_code,
        display_name=payload.display_name,
        ip_address=payload.ip_address,
        port=payload.port,
        opc_endpoint=payload.opc_endpoint,
        security_policy=payload.security_policy,
        security_mode=payload.security_mode,
        opc_username=payload.opc_username,
        opc_password_encrypted=encrypt_secret(payload.opc_password) if payload.opc_password else None,
        enabled=payload.enabled,
        status="draft",
        notes=payload.notes,
    )
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
