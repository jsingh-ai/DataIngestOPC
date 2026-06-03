from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from app.config import Settings, get_settings
from app.models import Machine
from app.security import decrypt_secret

try:
    from asyncua import Client  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    Client = None  # type: ignore[assignment]


@dataclass
class BrowseNode:
    opc_node_id: str
    browse_path: str
    display_name: str
    browse_name: str
    node_class: str
    data_type: str | None
    is_variable: bool


class OpcClientProtocol(Protocol):
    async def test_connection(self, machine: Machine) -> tuple[bool, str]: ...
    async def browse_tags(
        self,
        machine: Machine,
        max_depth: int,
        max_nodes: int,
        root_node_id: str | None = None,
        root_label: str | None = None,
    ) -> list[BrowseNode]: ...


class MockOpcClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.offline_codes = {
            code.strip() for code in self.settings.mock_opc_offline_machine_codes.split(",") if code.strip()
        }

    async def test_connection(self, machine: Machine) -> tuple[bool, str]:
        if self.settings.mock_opc_slow_ms:
            await asyncio.sleep(self.settings.mock_opc_slow_ms / 1000)
        if machine.machine_code in self.offline_codes:
            return False, "Machine is offline in mock OPC mode"
        return True, "Mock OPC connection successful"

    async def browse_tags(
        self,
        machine: Machine,
        max_depth: int,
        max_nodes: int,
        root_node_id: str | None = None,
        root_label: str | None = None,
    ) -> list[BrowseNode]:
        if machine.machine_code in self.offline_codes:
            raise TimeoutError("Machine is offline in mock OPC mode")
        if self.settings.mock_opc_slow_ms:
            await asyncio.sleep(self.settings.mock_opc_slow_ms / 1000)
        nodes: list[BrowseNode] = []
        root_prefix = root_label or "Root / Objects"
        if root_node_id is None:
            folder_names = ["PLC", "Modules", "Default", "Status", "Parameters"]
            for index, folder_name in enumerate(folder_names[: max_nodes]):
                nodes.append(
                    BrowseNode(
                        opc_node_id=f"ns=2;s={machine.machine_code}.{folder_name}",
                        browse_path=f"{root_prefix}/{folder_name}",
                        display_name=folder_name,
                        browse_name=folder_name,
                        node_class="Object",
                        data_type=None,
                        is_variable=False,
                    )
                )
            return nodes

        folder_names = [f"Folder {index}" for index in range(1, min(5, max_nodes // 3 + 1))]
        variable_count = max(0, min(self.settings.mock_opc_tag_count, max_nodes) - len(folder_names))
        for index, folder_name in enumerate(folder_names):
            nodes.append(
                BrowseNode(
                    opc_node_id=f"{root_node_id}.Group{index}",
                    browse_path=f"{root_prefix}/{folder_name}",
                    display_name=folder_name,
                    browse_name=folder_name.replace(" ", ""),
                    node_class="Object",
                    data_type=None,
                    is_variable=False,
                )
            )
        for index in range(variable_count):
            folder = f"Area{index % max(1, min(max_depth, 8))}"
            browse_path = f"{root_prefix}/{folder}/Tag{index}"
            nodes.append(
                BrowseNode(
                    opc_node_id=f"{root_node_id}.Tag{index}",
                    browse_path=browse_path,
                    display_name=f"Tag {index}",
                    browse_name=f"Tag{index}",
                    node_class="Variable",
                    data_type="Double" if index % 2 == 0 else "Boolean",
                    is_variable=True,
                )
            )
        return nodes


class AsyncUaOpcClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _normalize_security_policy(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.split("#")[-1].replace("http://opcfoundation.org/UA/SecurityPolicy#", "")
        return None if normalized.lower() == "none" else normalized

    def _normalize_security_mode(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.split("_")[-1]
        return None if normalized.lower() == "none" else normalized

    async def _configure_client(self, machine: Machine, timeout_seconds: float) -> Any:
        if Client is None:
            raise RuntimeError("asyncua not installed")
        client = Client(url=machine.opc_endpoint, timeout=timeout_seconds)
        username = machine.opc_username
        password = decrypt_secret(machine.opc_password_encrypted)
        if username:
            client.set_user(username)
        if password:
            client.set_password(password)
        security_policy = self._normalize_security_policy(machine.security_policy)
        security_mode = self._normalize_security_mode(machine.security_mode)
        if security_policy and security_mode:
            if not (self.settings.opc_client_certificate_path and self.settings.opc_client_private_key_path):
                raise ValueError(
                    "Machine requires OPC client certificate settings for secure connection"
                )
            key_path = self.settings.opc_client_private_key_path
            if self.settings.opc_client_private_key_password:
                key_path = f"{key_path}::{self.settings.opc_client_private_key_password}"
            parts = [
                security_policy,
                security_mode,
                self.settings.opc_client_certificate_path,
                key_path,
            ]
            if self.settings.opc_server_certificate_path:
                parts.append(self.settings.opc_server_certificate_path)
            await client.set_security_string(",".join(parts))
        return client

    async def test_connection(self, machine: Machine) -> tuple[bool, str]:
        client = await self._configure_client(machine, self.settings.opc_connect_timeout_seconds)
        try:
            await asyncio.wait_for(client.connect(), timeout=self.settings.opc_connect_timeout_seconds)
            await asyncio.wait_for(client.nodes.root.get_children(), timeout=self.settings.opc_connect_timeout_seconds)
            return True, "Connected and browsed root successfully"
        except Exception as exc:
            return False, f"Connection failed: {exc}"
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def browse_tags(
        self,
        machine: Machine,
        max_depth: int,
        max_nodes: int,
        root_node_id: str | None = None,
        root_label: str | None = None,
    ) -> list[BrowseNode]:
        client = await self._configure_client(machine, self.settings.opc_browse_timeout_seconds)
        discovered: list[BrowseNode] = []
        await asyncio.wait_for(client.connect(), timeout=self.settings.opc_connect_timeout_seconds)
        try:
            if root_node_id:
                start_node = client.get_node(root_node_id)
                start_path = root_label or root_node_id
            else:
                start_node = client.nodes.objects
                start_path = root_label or "Root/Objects"
            children = await asyncio.wait_for(
                getattr(start_node, "get_children")(), timeout=self.settings.opc_browse_timeout_seconds
            )
            for child in children:
                if len(discovered) >= max_nodes:
                    break
                try:
                    browse_name = await asyncio.wait_for(child.read_browse_name(), timeout=self.settings.opc_browse_timeout_seconds)
                    display_name = await asyncio.wait_for(child.read_display_name(), timeout=self.settings.opc_browse_timeout_seconds)
                    node_class = (await asyncio.wait_for(child.read_node_class(), timeout=self.settings.opc_browse_timeout_seconds)).name
                except Exception:
                    continue
                child_path = f"{start_path}/{browse_name.Name}"
                is_variable = node_class == "Variable"
                data_type = None
                if is_variable:
                    try:
                        variant = await asyncio.wait_for(
                            child.read_data_type_as_variant_type(),
                            timeout=self.settings.opc_browse_timeout_seconds,
                        )
                        data_type = getattr(variant, "name", str(variant))
                    except Exception:
                        data_type = None
                discovered.append(
                    BrowseNode(
                        opc_node_id=child.nodeid.to_string(),
                        browse_path=child_path,
                        display_name=display_name.Text,
                        browse_name=browse_name.Name,
                        node_class=node_class,
                        data_type=data_type,
                        is_variable=is_variable,
                    )
                )
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        return discovered


def get_opc_service() -> OpcClientProtocol:
    settings = get_settings()
    if settings.use_mock_opc:
        return MockOpcClient(settings)
    return AsyncUaOpcClient(settings)
