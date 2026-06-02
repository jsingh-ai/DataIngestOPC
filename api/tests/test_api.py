import pytest
from fastapi import HTTPException

from app.auth import get_current_user
from app.config import get_settings
from app.models import CollectorConfigState
from app.security import decrypt_secret, encrypt_secret, hash_password, verify_password
from app.routers import browse, collector, machines, tags
from app.schemas import AddTagsFromCacheRequest, BrowseRequest, MachineCreate, MachineUpdate, TagCreate


def test_auth_required_invalid_token():
    with pytest.raises(HTTPException) as exc:
        get_current_user(token="bad-token", settings=get_settings())
    assert exc.value.status_code == 401


def test_password_hash_and_secret_encryption():
    password_hash = hash_password("secret-123")
    assert verify_password("secret-123", password_hash)
    encrypted = encrypt_secret("opc-pass")
    assert decrypt_secret(encrypted) == "opc-pass"


def test_machine_crud_and_password_hidden(session):
    machine = machines.create_machine_route(
        MachineCreate(
            machine_code="M01",
            display_name="Machine 01",
            ip_address="10.0.0.1",
            port=4840,
            opc_endpoint="opc.tcp://10.0.0.1:4840",
            opc_username="user1",
            opc_password="secret",
            enabled=False,
        ),
        db=session,
        user="test-admin",
    )
    assert machine.machine_id > 0
    assert not hasattr(machine, "opc_password")

    listed = machines.list_machines(db=session, page=1, page_size=100, search=None, _="test-admin")
    assert listed.total == 1

    updated = machines.patch_machine(
        machine.machine_id,
        MachineUpdate(display_name="Updated"),
        db=session,
        user="test-admin",
    )
    assert updated.display_name == "Updated"


def test_tag_crud_and_pagination(session):
    machine = machines.create_machine_route(
        MachineCreate(
            machine_code="M02",
            display_name="Machine 02",
            ip_address="10.0.0.2",
            port=4840,
            opc_endpoint="opc.tcp://10.0.0.2:4840",
            enabled=True,
        ),
        db=session,
        user="test-admin",
    )
    for index in range(3):
        created = tags.create_tag_route(
            machine.machine_id,
            TagCreate(
                tag_key=f"tag_{index}",
                display_name=f"Tag {index}",
                opc_node_id=f"ns=2;s=M02.Tag{index}",
                enabled=True,
            ),
            db=session,
            user="test-admin",
        )
        assert created.tag_id > 0
    listed = tags.list_tags(
        machine.machine_id,
        db=session,
        page=1,
        page_size=2,
        search=None,
        enabled=None,
        folder_path=None,
        _="test-admin",
    )
    assert listed.page_size == 2
    assert len(listed.items) == 2


@pytest.mark.asyncio
async def test_connection_test_and_browse_cache(session):
    machine = machines.create_machine_route(
        MachineCreate(
            machine_code="M03",
            display_name="Machine 03",
            ip_address="10.0.0.3",
            port=4840,
            opc_endpoint="opc.tcp://10.0.0.3:4840",
            enabled=True,
        ),
        db=session,
        user="test-admin",
    )
    test_response = await machines.test_connection(machine.machine_id, db=session, _="test-admin")
    assert test_response.success is True
    browse_response = await machines.browse_tags(
        machine.machine_id,
        BrowseRequest(max_nodes=10, max_depth=3),
        db=session,
        user="test-admin",
    )
    assert browse_response.discovered_count == 10
    cache = browse.list_browse_cache(
        machine.machine_id,
        db=session,
        page=1,
        page_size=5,
        search=None,
        folder_path=None,
        is_variable=True,
        already_added=False,
        _="test-admin",
    )
    assert cache.total == 10


@pytest.mark.asyncio
async def test_add_tags_from_cache_and_reload(session):
    machine = machines.create_machine_route(
        MachineCreate(
            machine_code="M04",
            display_name="Machine 04",
            ip_address="10.0.0.4",
            port=4840,
            opc_endpoint="opc.tcp://10.0.0.4:4840",
            enabled=True,
        ),
        db=session,
        user="test-admin",
    )
    await machines.browse_tags(machine.machine_id, BrowseRequest(max_nodes=2), db=session, user="test-admin")
    cache_items = browse.list_browse_cache(
        machine.machine_id,
        db=session,
        page=1,
        page_size=100,
        search=None,
        folder_path=None,
        _="test-admin",
    ).items
    add_response = browse.add_tags_from_cache(
        machine.machine_id,
        AddTagsFromCacheRequest(
            tags=[{"cache_id": cache_items[0].cache_id}, {"cache_id": cache_items[1].cache_id}]
        ),
        db=session,
        _="test-admin",
    )
    assert add_response.created_count == 2
    reload_response = collector.reload_config(db=session, user="test-admin")
    assert reload_response.active_config_version == 2
    state = session.get(CollectorConfigState, 1)
    assert state is not None
    assert state.pending_reload is True
    restart_response = collector.restart_collector(db=session, user="test-admin")
    assert restart_response.command_type == "restart_collector"
