from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime
from collections.abc import Coroutine

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Machine, MachineCollectionStatus, TagBrowserCache, TagDefinition
from app.schemas import (
    BrowseRequest,
    BrowseSummaryResponse,
    ConnectionTestResponse,
    MachineCreate,
    MachineSummary,
    MachineUpdate,
    PaginatedResponse,
)
from app.services.command_service import enqueue_command
from app.services.machine_service import (
    build_machine_from_payload,
    build_machine_query,
    create_machine,
    machine_status_map,
    machine_tag_counts,
    update_machine,
)
from app.services.opcua_service import get_opc_service

router = APIRouter(prefix="/api/machines", tags=["machines"])
logger = logging.getLogger("opc_platform.api.machines")


def _run_coro_sync(coro: Coroutine[object, object, tuple[bool, str]]) -> tuple[bool, str]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[tuple[bool, str]] = []
    error: list[BaseException] = []

    def _runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # pragma: no cover - thread handoff
            error.append(exc)

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


@router.get("", response_model=PaginatedResponse)
def list_machines(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> PaginatedResponse:
    query = build_machine_query(search)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    tag_counts = machine_tag_counts(db)
    statuses = machine_status_map(db)
    result = []
    for machine in items:
        status_row = statuses.get(machine.machine_id)
        result.append(
            MachineSummary.model_validate(
                {
                    **machine.__dict__,
                    "tag_count": tag_counts.get(machine.machine_id, 0),
                    "online_status": "online" if status_row and status_row.opc_connected else "offline",
                    "last_heartbeat_ts_utc": status_row.last_heartbeat_ts_utc if status_row else None,
                }
            )
        )
    return PaginatedResponse(items=result, total=total, page=page, page_size=page_size)


@router.post("", response_model=MachineSummary, status_code=status.HTTP_201_CREATED)
def create_machine_route(
    payload: MachineCreate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> MachineSummary:
    logger.info(
        "machine_create_received user=%s machine_code=%s display_name=%s endpoint=%s username_present=%s",
        user,
        (payload.machine_code or "").strip() or "<auto>",
        payload.display_name,
        payload.opc_endpoint,
        bool(payload.opc_username),
    )
    machine = build_machine_from_payload(payload)
    logger.info(
        "machine_create_step=opc_test_start machine_code=%s endpoint=%s",
        machine.machine_code,
        machine.opc_endpoint,
    )
    success, message = _run_coro_sync(get_opc_service().test_connection(machine))
    if not success:
        logger.warning(
            "machine_create_step=opc_test_failed machine_code=%s endpoint=%s error=%s",
            machine.machine_code,
            machine.opc_endpoint,
            message,
        )
        raise HTTPException(status_code=400, detail=f"Machine connection test failed: {message}")
    logger.info("machine_create_step=opc_test_success machine_code=%s endpoint=%s", machine.machine_code, machine.opc_endpoint)
    created = create_machine(db, payload, user, status="connection_tested")
    logger.info(
        "machine_create_step=database_saved machine_id=%s machine_code=%s status=%s enabled=%s",
        created.machine_id,
        created.machine_code,
        created.status,
        created.enabled,
    )
    return MachineSummary.model_validate({**created.__dict__, "tag_count": 0, "online_status": "unknown"})


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection_preview(
    payload: MachineCreate,
    _: str = Depends(get_current_user),
) -> ConnectionTestResponse:
    logger.info(
        "machine_test_preview_received machine_code=%s display_name=%s endpoint=%s username_present=%s",
        (payload.machine_code or "").strip() or "<auto>",
        payload.display_name,
        payload.opc_endpoint,
        bool(payload.opc_username),
    )
    machine = build_machine_from_payload(payload)
    logger.info(
        "machine_test_preview_step=opc_test_start machine_code=%s endpoint=%s",
        machine.machine_code,
        machine.opc_endpoint,
    )
    success, message = await get_opc_service().test_connection(machine)
    if success:
        logger.info(
            "machine_test_preview_step=opc_test_success machine_code=%s endpoint=%s",
            machine.machine_code,
            machine.opc_endpoint,
        )
    else:
        logger.warning(
            "machine_test_preview_step=opc_test_failed machine_code=%s endpoint=%s error=%s",
            machine.machine_code,
            machine.opc_endpoint,
            message,
        )
    return ConnectionTestResponse(
        success=success,
        message=message,
        machine_status="connection_tested" if success else "error",
    )


@router.get("/{machine_id}", response_model=MachineSummary)
def get_machine(machine_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)) -> MachineSummary:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    tag_count = db.scalar(select(func.count(TagDefinition.tag_id)).where(TagDefinition.machine_id == machine_id)) or 0
    status_row = db.get(MachineCollectionStatus, machine_id)
    return MachineSummary.model_validate(
        {
            **machine.__dict__,
            "tag_count": tag_count,
            "online_status": "online" if status_row and status_row.opc_connected else "offline",
            "last_heartbeat_ts_utc": status_row.last_heartbeat_ts_utc if status_row else None,
        }
    )


@router.patch("/{machine_id}", response_model=MachineSummary)
def patch_machine(
    machine_id: int,
    payload: MachineUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> MachineSummary:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    updated = update_machine(db, machine, payload, user)
    status_row = db.get(MachineCollectionStatus, machine_id)
    return MachineSummary.model_validate(
        {
            **updated.__dict__,
            "tag_count": 0,
            "online_status": "online" if status_row and status_row.opc_connected else "offline",
            "last_heartbeat_ts_utc": status_row.last_heartbeat_ts_utc if status_row else None,
        }
    )


@router.post("/{machine_id}/enable", response_model=MachineSummary)
def enable_machine(machine_id: int, db: Session = Depends(get_db), user: str = Depends(get_current_user)) -> MachineSummary:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    updated = update_machine(db, machine, MachineUpdate(enabled=True, status="active"), user)
    return MachineSummary.model_validate({**updated.__dict__, "tag_count": 0, "online_status": "unknown"})


@router.post("/{machine_id}/disable", response_model=MachineSummary)
def disable_machine(machine_id: int, db: Session = Depends(get_db), user: str = Depends(get_current_user)) -> MachineSummary:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    updated = update_machine(db, machine, MachineUpdate(enabled=False, status="disabled"), user)
    return MachineSummary.model_validate({**updated.__dict__, "tag_count": 0, "online_status": "unknown"})


@router.post("/{machine_id}/test-connection", response_model=ConnectionTestResponse)
async def test_connection(machine_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)) -> ConnectionTestResponse:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    logger.info(
        "machine_test_existing_received machine_id=%s machine_code=%s endpoint=%s",
        machine.machine_id,
        machine.machine_code,
        machine.opc_endpoint,
    )
    logger.info("machine_test_existing_step=opc_test_start machine_id=%s machine_code=%s", machine.machine_id, machine.machine_code)
    success, message = await get_opc_service().test_connection(machine)
    machine.status = "connection_tested" if success else "error"
    machine.updated_at = datetime.now(UTC)
    db.commit()
    if success:
        logger.info(
            "machine_test_existing_step=opc_test_success machine_id=%s machine_code=%s status=%s",
            machine.machine_id,
            machine.machine_code,
            machine.status,
        )
    else:
        logger.warning(
            "machine_test_existing_step=opc_test_failed machine_id=%s machine_code=%s error=%s",
            machine.machine_id,
            machine.machine_code,
            message,
        )
    return ConnectionTestResponse(
        success=success,
        message=message,
        machine_status=machine.status,
    )


@router.post("/{machine_id}/browse-tags", response_model=BrowseSummaryResponse)
async def browse_tags(
    machine_id: int,
    payload: BrowseRequest,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
) -> BrowseSummaryResponse:
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    opc = get_opc_service()
    nodes = await opc.browse_tags(
        machine,
        payload.max_depth or 6,
        payload.max_nodes or 5000,
        payload.root_node_id,
        payload.root_label,
    )
    tag_nodes = {
        row[0]
        for row in db.execute(select(TagDefinition.opc_node_id).where(TagDefinition.machine_id == machine_id)).all()
    }
    upserts = 0
    variables = 0
    now = datetime.now(UTC)
    for node in nodes:
        variables += int(node.is_variable)
        cache_row = db.execute(
            select(TagBrowserCache).where(
                TagBrowserCache.machine_id == machine_id, TagBrowserCache.opc_node_id == node.opc_node_id
            )
        ).scalar_one_or_none()
        if cache_row is None:
            cache_row = TagBrowserCache(machine_id=machine_id, opc_node_id=node.opc_node_id)
            db.add(cache_row)
        cache_row.browse_path = node.browse_path
        cache_row.display_name = node.display_name
        cache_row.browse_name = node.browse_name
        cache_row.node_class = node.node_class
        cache_row.data_type = node.data_type
        cache_row.is_variable = node.is_variable
        cache_row.already_added = node.opc_node_id in tag_nodes
        cache_row.last_seen_at = now
        upserts += 1
    command, _ = enqueue_command(
        db, "browse_machine_tags", user, command_payload={"machine_id": machine_id, "discovered_count": len(nodes)}
    )
    command.status = "completed"
    command.completed_at = now
    command.result_message = f"Browse cached {len(nodes)} nodes"
    db.commit()
    return BrowseSummaryResponse(
        discovered_count=len(nodes),
        variable_count=variables,
        cache_upserts=upserts,
        message="Browse cache refreshed",
    )
