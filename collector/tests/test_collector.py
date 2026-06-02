from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from collector.config import CollectorSettings
from collector.main import CollectorApp
from collector.models import MachineConfig, NodeReadResult, SampleRecord
from collector.normalization import normalize_value
from collector.opcua_client import AsyncUaReader, MachineBackoffError, MockOpcReader
from collector.sqlite_buffer import SqliteBuffer


def build_settings() -> CollectorSettings:
    settings = CollectorSettings()
    settings.db_host = "localhost"
    settings.db_name = "opc_platform"
    settings.db_user = "opc_user"
    settings.db_password = "secret"
    settings.password_encryption_key = "test-password-key-32-bytes-minimum"
    return settings


def test_value_normalization():
    assert normalize_value(12.5) == (12.5, None, None)
    assert normalize_value(True) == (None, None, True)
    assert normalize_value("abc") == (None, "abc", None)


def test_opc_read_only_api_surface():
    settings = build_settings()
    settings.use_mock_opc = True
    reader = MockOpcReader(settings)
    real_reader = AsyncUaReader(settings, client_factory=lambda **_: None)
    for obj in (reader, real_reader):
        write_methods = [name for name in dir(obj) if name.lower().startswith("write")]
        assert write_methods == []


@pytest.mark.asyncio
async def test_mock_opc_reader_contract():
    settings = build_settings()
    settings.use_mock_opc = True
    reader = MockOpcReader(settings)
    machine = MachineConfig(1, "M01", "Machine", "opc.tcp://127.0.0.1:4840", None, None, None, None, True)
    results = await reader.read_nodes(machine, ["ns=2;s=M01.Tag1", "ns=2;s=M01.Tag2"])
    assert len(results) == 2
    assert all(isinstance(result, NodeReadResult) for result in results)


@pytest.mark.asyncio
async def test_mock_opc_reader_offline_machine():
    settings = build_settings()
    settings.mock_opc_offline_machine_codes = "OFF01"
    reader = MockOpcReader(settings)
    machine = MachineConfig(1, "OFF01", "Offline", "opc.tcp://127.0.0.1:4840", None, None, None, None, True)
    with pytest.raises(MachineBackoffError):
        await reader.read_nodes(machine, ["ns=2;s=OFF01.Tag1"])


def test_sqlite_buffer_insert_flush_delete_and_failure(tmp_path):
    buffer = SqliteBuffer(str(tmp_path / "buffer.sqlite3"))
    sample = SampleRecord(
        sample_ts_utc=datetime.now(UTC),
        machine_id=1,
        tag_id=1,
        value_num=1.23,
        value_str=None,
        value_bool=None,
        quality_code="Good",
        source_ts_utc=datetime.now(UTC),
        ingest_ts_utc=datetime.now(UTC),
    )
    buffer.insert_samples([sample])
    batch = buffer.fetch_batch(10)
    assert len(batch) == 1
    buffer.mark_flush_failure([batch[0]["buffer_id"]], "db down")
    failed = buffer.fetch_batch(10)[0]
    assert failed["flush_attempt_count"] == 1
    buffer.delete_batch([batch[0]["buffer_id"]])
    assert buffer.row_count() == 0
    buffer.close()


def test_flush_buffer_leaves_rows_intact_on_writer_failure(tmp_path):
    buffer = SqliteBuffer(str(tmp_path / "buffer.sqlite3"))
    sample = SampleRecord(
        sample_ts_utc=datetime.now(UTC),
        machine_id=1,
        tag_id=1,
        value_num=1.23,
        value_str=None,
        value_bool=None,
        quality_code="Good",
        source_ts_utc=datetime.now(UTC),
        ingest_ts_utc=datetime.now(UTC),
    )
    buffer.insert_samples([sample])

    app = object.__new__(CollectorApp)
    app.settings = SimpleNamespace(collector_mysql_batch_size=100)
    app.buffer = buffer
    app.total_flush_batches = 0
    app.total_flush_failures = 0

    class FailingWriter:
        def write_batch(self, rows: list[dict]) -> None:
            raise RuntimeError("mysql down")

    app.writer = FailingWriter()
    flushed = CollectorApp.flush_buffer_once(app)
    assert flushed == 0
    assert buffer.row_count() == 1
    buffer.close()


def test_flush_buffer_success_deletes_rows(tmp_path):
    buffer = SqliteBuffer(str(tmp_path / "buffer.sqlite3"))
    sample = SampleRecord(
        sample_ts_utc=datetime.now(UTC),
        machine_id=1,
        tag_id=1,
        value_num=1.23,
        value_str=None,
        value_bool=None,
        quality_code="Good",
        source_ts_utc=datetime.now(UTC),
        ingest_ts_utc=datetime.now(UTC),
    )
    buffer.insert_samples([sample])

    app = object.__new__(CollectorApp)
    app.settings = SimpleNamespace(collector_mysql_batch_size=100)
    app.buffer = buffer
    app.total_flush_batches = 0
    app.total_flush_failures = 0

    class GoodWriter:
        def write_batch(self, rows: list[dict]) -> None:
            assert len(rows) == 1

    app.writer = GoodWriter()
    flushed = CollectorApp.flush_buffer_once(app)
    assert flushed == 1
    assert buffer.row_count() == 0
    buffer.close()


def test_aligned_sample_timestamp():
    app = object.__new__(CollectorApp)
    sample_ts = CollectorApp._aligned_sample_ts(app, datetime(2026, 1, 1, 0, 1, 44, tzinfo=UTC), 60)
    assert sample_ts.second == 0


@pytest.mark.asyncio
async def test_asyncua_reader_uses_real_read_path_with_fallback(monkeypatch):
    class FakeStatusCode:
        def __init__(self, name: str, bad: bool = False) -> None:
            self.name = name
            self._bad = bad

        def is_bad(self) -> bool:
            return self._bad

    class FakeVariant:
        def __init__(self, value: object) -> None:
            self.Value = value

    class FakeDataValue:
        def __init__(self, value: object, bad: bool = False) -> None:
            self.Value = FakeVariant(value)
            self.StatusCode = FakeStatusCode("Bad" if bad else "Good", bad)
            self.SourceTimestamp = datetime.now(UTC)
            self.ServerTimestamp = datetime.now(UTC)

    class FakeNode:
        def __init__(self, node_id: str) -> None:
            self.node_id = node_id

        async def read_data_value(self) -> FakeDataValue:
            return FakeDataValue(42.0 if self.node_id.endswith("1") else True)

    class FakeClient:
        def __init__(self, **_: object) -> None:
            self.connected = False

        def set_user(self, _: str) -> None:
            return None

        def set_password(self, _: str) -> None:
            return None

        async def connect(self) -> None:
            self.connected = True

        async def disconnect(self) -> None:
            self.connected = False

        def get_node(self, node_id: str) -> FakeNode:
            return FakeNode(node_id)

        async def read_attributes(self, nodes: list[FakeNode], attr: object) -> list[FakeDataValue]:
            del nodes, attr
            raise RuntimeError("batch read unavailable")

    monkeypatch.setattr("collector.opcua_client.ua", SimpleNamespace(AttributeIds=SimpleNamespace(Value=13)))

    settings = build_settings()
    reader = AsyncUaReader(settings, client_factory=FakeClient)
    machine = MachineConfig(1, "M01", "Machine", "opc.tcp://127.0.0.1:4840", None, None, None, None, True)
    results = await reader.read_nodes(machine, ["ns=2;s=M01.Tag1", "ns=2;s=M01.Tag2"])
    assert [result.ok for result in results] == [True, True]
    await reader.shutdown()


@pytest.mark.asyncio
async def test_asyncua_reader_test_connection_and_disconnect(monkeypatch):
    class FakeRoot:
        async def get_children(self) -> list[int]:
            return [1, 2, 3]

    class FakeNode:
        async def read_data_value(self) -> SimpleNamespace:
            return SimpleNamespace(
                Value=SimpleNamespace(Value=12.0),
                StatusCode=SimpleNamespace(name="Good", is_bad=lambda: False),
                SourceTimestamp=datetime.now(UTC),
                ServerTimestamp=datetime.now(UTC),
            )

    class FakeClient:
        def __init__(self, **_: object) -> None:
            self.nodes = SimpleNamespace(root=FakeRoot())

        def set_user(self, _: str) -> None:
            return None

        def set_password(self, _: str) -> None:
            return None

        async def connect(self) -> None:
            return None

        async def disconnect(self) -> None:
            return None

        def get_node(self, _: str) -> FakeNode:
            return FakeNode()

    monkeypatch.setattr("collector.opcua_client.ua", SimpleNamespace(AttributeIds=SimpleNamespace(Value=13)))

    settings = build_settings()
    reader = AsyncUaReader(settings, client_factory=FakeClient)
    machine = MachineConfig(1, "M01", "Machine", "opc.tcp://127.0.0.1:4840", None, None, None, None, True)
    success, message = await reader.test_connection(machine, node_id="ns=2;s=M01.Tag1")
    assert success is True
    assert "read node" in message
    await reader.shutdown()
