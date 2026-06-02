from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from collector.config import CollectorSettings
from collector.models import MachineConfig, NodeReadResult

try:
    from asyncua import Client, ua  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    Client = None  # type: ignore[assignment]
    ua = None  # type: ignore[assignment]

logger = logging.getLogger("opc_platform.collector.opcua")


class MachineBackoffError(RuntimeError):
    pass


@dataclass(slots=True)
class MachineSession:
    client: Any | None = None
    connected: bool = False
    backoff_seconds: int = 0
    next_retry_monotonic: float = 0.0
    last_error_message: str | None = None


class MockOpcReader:
    def __init__(self, settings: CollectorSettings) -> None:
        self.settings = settings
        self.offline_codes = {
            code.strip() for code in settings.mock_opc_offline_machine_codes.split(",") if code.strip()
        }

    async def sync_machines(self, active_machine_ids: set[int]) -> None:
        return None

    async def test_connection(self, machine: MachineConfig, node_id: str | None = None) -> tuple[bool, str]:
        if machine.machine_code in self.offline_codes:
            return False, f"{machine.machine_code} is offline"
        if node_id:
            results = await self.read_nodes(machine, [node_id])
            result = results[0]
            if result.ok:
                return True, f"Mock OPC connection successful and node {node_id} was read"
            return False, result.error_message or f"Mock OPC node {node_id} read failed"
        return True, "Mock OPC connection successful"

    async def browse_nodes(self, machine: MachineConfig, max_depth: int, max_nodes: int) -> list[dict[str, Any]]:
        if machine.machine_code in self.offline_codes:
            raise MachineBackoffError(f"{machine.machine_code} is offline")
        count = min(self.settings.mock_opc_tag_count, max_nodes)
        discovered: list[dict[str, Any]] = []
        for index in range(count):
            folder = f"Area{index % max(1, min(max_depth, 8))}"
            discovered.append(
                {
                    "opc_node_id": f"ns=2;s={machine.machine_code}.Tag{index}",
                    "browse_path": f"Root/Objects/{folder}/Tag{index}",
                    "display_name": f"Tag {index}",
                    "browse_name": f"Tag{index}",
                    "node_class": "Variable",
                    "data_type": "Double" if index % 2 == 0 else "Boolean",
                    "is_variable": True,
                }
            )
        return discovered

    async def read_nodes(self, machine: MachineConfig, node_ids: list[str]) -> list[NodeReadResult]:
        if machine.machine_code in self.offline_codes:
            raise MachineBackoffError(f"{machine.machine_code} is offline")
        if self.settings.mock_opc_slow_ms:
            await asyncio.sleep(self.settings.mock_opc_slow_ms / 1000)
        results: list[NodeReadResult] = []
        for node_id in node_ids:
            if random.random() < self.settings.mock_opc_failed_tag_rate:
                results.append(
                    NodeReadResult(
                        ok=False,
                        value=None,
                        quality_code="Bad",
                        source_ts_utc=datetime.now(UTC),
                        server_ts_utc=datetime.now(UTC),
                        error_message="Mock failed read",
                    )
                )
                continue
            number = abs(hash((machine.machine_code, node_id, int(time.time())))) % 1000
            value: Any = float(number) if number % 2 == 0 else bool(number % 3)
            results.append(
                NodeReadResult(
                    ok=True,
                    value=value,
                    quality_code="Good",
                    source_ts_utc=datetime.now(UTC),
                    server_ts_utc=datetime.now(UTC),
                    error_message=None,
                )
            )
        return results

    async def disconnect_machine(self, machine_id: int) -> None:
        return None

    async def shutdown(self) -> None:
        return None


class AsyncUaReader:
    def __init__(self, settings: CollectorSettings, client_factory: Callable[..., Any] | None = None) -> None:
        self.settings = settings
        self.client_factory = client_factory or Client
        self.sessions: dict[int, MachineSession] = {}

    async def sync_machines(self, active_machine_ids: set[int]) -> None:
        for machine_id in list(self.sessions):
            if machine_id not in active_machine_ids:
                await self.disconnect_machine(machine_id)

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

    async def _build_client(self, machine: MachineConfig) -> Any:
        if self.client_factory is None or ua is None:
            raise RuntimeError("asyncua not installed")
        client = self.client_factory(
            url=machine.opc_endpoint,
            timeout=self.settings.collector_opc_connect_timeout_seconds,
        )
        if machine.opc_username:
            client.set_user(machine.opc_username)
        if machine.opc_password:
            client.set_password(machine.opc_password)
        security_policy = self._normalize_security_policy(machine.security_policy)
        security_mode = self._normalize_security_mode(machine.security_mode)
        if security_policy and security_mode:
            if not (self.settings.opc_client_certificate_path and self.settings.opc_client_private_key_path):
                raise ValueError(
                    "OPC security requires OPC_CLIENT_CERTIFICATE_PATH and OPC_CLIENT_PRIVATE_KEY_PATH"
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

    async def _read_batch_values(self, client: Any, nodes: list[Any]) -> list[Any]:
        if hasattr(client, "read_attributes"):
            return await asyncio.wait_for(
                client.read_attributes(nodes, attr=ua.AttributeIds.Value),
                timeout=self.settings.collector_opc_read_timeout_seconds,
            )
        return [await self._read_single_value(node) for node in nodes]

    async def _read_single_value(self, node: Any) -> Any:
        return await asyncio.wait_for(
            node.read_data_value(),
            timeout=self.settings.collector_opc_read_timeout_seconds,
        )

    def _parse_data_value(self, node_id: str, data_value: Any) -> NodeReadResult:
        try:
            status_code = getattr(data_value, "StatusCode", None)
            quality_code = status_code.name if status_code is not None else "Unknown"
            is_good = bool(status_code is None or not status_code.is_bad())
            variant = getattr(getattr(data_value, "Value", None), "Value", None)
            source_ts = getattr(data_value, "SourceTimestamp", None)
            server_ts = getattr(data_value, "ServerTimestamp", None)
            return NodeReadResult(
                ok=is_good,
                value=variant,
                quality_code=quality_code,
                source_ts_utc=source_ts,
                server_ts_utc=server_ts,
                error_message=None if is_good else f"Bad quality: {quality_code}",
            )
        except Exception as exc:
            return NodeReadResult(
                ok=False,
                value=None,
                quality_code="Bad",
                source_ts_utc=None,
                server_ts_utc=None,
                error_message=f"Failed to parse node {node_id}: {exc}",
            )

    async def test_connection(self, machine: MachineConfig, node_id: str | None = None) -> tuple[bool, str]:
        session = await self._connect(machine)
        assert session.client is not None
        try:
            if node_id:
                node = session.client.get_node(node_id)
                data_value = await self._read_single_value(node)
                result = self._parse_data_value(node_id, data_value)
                if result.ok:
                    return True, f"Connected and read node {node_id} successfully"
                return False, result.error_message or f"Connected but node {node_id} returned bad quality"

            root_children = await asyncio.wait_for(
                session.client.nodes.root.get_children(),
                timeout=self.settings.collector_opc_browse_timeout_seconds,
            )
            return True, f"Connected and browsed root successfully ({len(root_children)} children)"
        except Exception as exc:
            await self._handle_connection_failure(machine, session, exc)
            return False, str(exc)

    async def browse_nodes(self, machine: MachineConfig, max_depth: int, max_nodes: int) -> list[dict[str, Any]]:
        session = await self._connect(machine)
        assert session.client is not None
        queue: deque[tuple[Any, str, int]] = deque([(session.client.nodes.objects, "Root/Objects", 0)])
        discovered: list[dict[str, Any]] = []
        try:
            while queue and len(discovered) < max_nodes:
                node, path, depth = queue.popleft()
                children = await asyncio.wait_for(
                    node.get_children(),
                    timeout=self.settings.collector_opc_browse_timeout_seconds,
                )
                for child in children:
                    if len(discovered) >= max_nodes:
                        break
                    try:
                        browse_name = await asyncio.wait_for(
                            child.read_browse_name(),
                            timeout=self.settings.collector_opc_browse_timeout_seconds,
                        )
                        display_name = await asyncio.wait_for(
                            child.read_display_name(),
                            timeout=self.settings.collector_opc_browse_timeout_seconds,
                        )
                        node_class = (
                            await asyncio.wait_for(
                                child.read_node_class(),
                                timeout=self.settings.collector_opc_browse_timeout_seconds,
                            )
                        ).name
                    except Exception as exc:
                        logger.warning(
                            "opc_browse_node_failed machine_code=%s machine_id=%s error=%s",
                            machine.machine_code,
                            machine.machine_id,
                            exc,
                        )
                        continue

                    child_path = f"{path}/{browse_name.Name}"
                    is_variable = node_class == "Variable"
                    data_type: str | None = None
                    if is_variable:
                        try:
                            variant = await asyncio.wait_for(
                                child.read_data_type_as_variant_type(),
                                timeout=self.settings.collector_opc_browse_timeout_seconds,
                            )
                            data_type = getattr(variant, "name", str(variant))
                        except Exception:
                            data_type = None
                    discovered.append(
                        {
                            "opc_node_id": child.nodeid.to_string(),
                            "browse_path": child_path,
                            "display_name": display_name.Text,
                            "browse_name": browse_name.Name,
                            "node_class": node_class,
                            "data_type": data_type,
                            "is_variable": is_variable,
                        }
                    )
                    if depth + 1 < max_depth and node_class in {"Object", "FolderType"}:
                        queue.append((child, child_path, depth + 1))
            return discovered
        except Exception as exc:
            await self._handle_connection_failure(machine, session, exc)
            raise

    async def _connect(self, machine: MachineConfig) -> MachineSession:
        now_monotonic = time.monotonic()
        session = self.sessions.setdefault(machine.machine_id, MachineSession())
        if session.connected and session.client is not None:
            return session
        if now_monotonic < session.next_retry_monotonic:
            raise MachineBackoffError(
                f"Machine {machine.machine_code} in backoff for {session.next_retry_monotonic - now_monotonic:.1f}s"
            )
        try:
            session.client = await self._build_client(machine)
            await asyncio.wait_for(
                session.client.connect(),
                timeout=self.settings.collector_opc_connect_timeout_seconds,
            )
            session.connected = True
            session.backoff_seconds = self.settings.collector_machine_backoff_initial_seconds
            session.next_retry_monotonic = 0.0
            session.last_error_message = None
            return session
        except Exception as exc:
            await self._handle_connection_failure(machine, session, exc)
            raise

    async def _handle_connection_failure(
        self, machine: MachineConfig, session: MachineSession, exc: Exception
    ) -> None:
        session.last_error_message = str(exc)
        if session.client is not None:
            try:
                await session.client.disconnect()
            except Exception:
                pass
        session.client = None
        session.connected = False
        next_backoff = session.backoff_seconds or self.settings.collector_machine_backoff_initial_seconds
        session.backoff_seconds = min(next_backoff * 2, self.settings.collector_machine_backoff_max_seconds)
        session.next_retry_monotonic = time.monotonic() + next_backoff
        logger.warning(
            "opc_connect_failed machine_code=%s machine_id=%s error=%s backoff_seconds=%s",
            machine.machine_code,
            machine.machine_id,
            exc,
            next_backoff,
        )

    async def read_nodes(self, machine: MachineConfig, node_ids: list[str]) -> list[NodeReadResult]:
        session = await self._connect(machine)
        assert session.client is not None
        nodes = [session.client.get_node(node_id) for node_id in node_ids]
        try:
            data_values = await self._read_batch_values(session.client, nodes)
            return [
                self._parse_data_value(node_id, data_value)
                for node_id, data_value in zip(node_ids, data_values, strict=True)
            ]
        except Exception as batch_exc:
            logger.warning(
                "opc_batch_read_failed machine_code=%s machine_id=%s error=%s",
                machine.machine_code,
                machine.machine_id,
                batch_exc,
            )

        results: list[NodeReadResult] = []
        try:
            for node_id, node in zip(node_ids, nodes, strict=True):
                try:
                    data_value = await self._read_single_value(node)
                    results.append(self._parse_data_value(node_id, data_value))
                except Exception as exc:
                    results.append(
                        NodeReadResult(
                            ok=False,
                            value=None,
                            quality_code="Bad",
                            source_ts_utc=None,
                            server_ts_utc=None,
                            error_message=f"Failed to read node {node_id}: {exc}",
                        )
                    )
            return results
        except Exception as exc:
            await self._handle_connection_failure(machine, session, exc)
            raise

    async def disconnect_machine(self, machine_id: int) -> None:
        session = self.sessions.pop(machine_id, None)
        if session is None or session.client is None:
            return
        try:
            await asyncio.wait_for(
                session.client.disconnect(),
                timeout=self.settings.collector_opc_connect_timeout_seconds,
            )
        except Exception:
            logger.warning("opc_disconnect_failed machine_id=%s", machine_id)

    async def shutdown(self) -> None:
        for machine_id in list(self.sessions):
            await self.disconnect_machine(machine_id)


def get_reader(settings: CollectorSettings) -> MockOpcReader | AsyncUaReader:
    if settings.use_mock_opc:
        return MockOpcReader(settings)
    return AsyncUaReader(settings)
