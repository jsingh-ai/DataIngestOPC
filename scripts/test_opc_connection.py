from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from collector.config import CollectorSettings  # noqa: E402
from collector.models import MachineConfig  # noqa: E402
from collector.opcua_client import AsyncUaReader, MockOpcReader  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test an OPC UA endpoint without MySQL.")
    parser.add_argument("--endpoint", help="OPC UA endpoint URL, e.g. opc.tcp://host:4840")
    parser.add_argument("--security-policy")
    parser.add_argument("--security-mode")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--node-id", help="Optional node id to read after connect")
    parser.add_argument("--browse", action="store_true", help="Browse from Root/Objects after connect")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=100)
    parser.add_argument("--force-real", action="store_true", help="Ignore USE_MOCK_OPC from .env and use asyncua")
    return parser


async def run_test(args: argparse.Namespace) -> int:
    settings = CollectorSettings()
    if args.force_real:
        settings.use_mock_opc = False

    endpoint = args.endpoint or os.getenv("OPC_TEST_ENDPOINT")
    username = args.username or os.getenv("OPC_TEST_USERNAME")
    password = args.password or os.getenv("OPC_TEST_PASSWORD")
    security_policy = args.security_policy or os.getenv("OPC_TEST_SECURITY_POLICY")
    security_mode = args.security_mode or os.getenv("OPC_TEST_SECURITY_MODE")
    node_id = args.node_id or os.getenv("OPC_TEST_NODE_ID")
    if args.password:
        print("Warning: --password may be stored in shell history. Prefer OPC_TEST_PASSWORD or interactive prompt.", file=sys.stderr)
    if username and not password:
        password = getpass.getpass("OPC UA password: ")
    if not endpoint:
        if settings.use_mock_opc:
            endpoint = "opc.tcp://mock.local:4840"
        else:
            print("Missing endpoint. Provide --endpoint or define OPC_TEST_ENDPOINT in the environment.", file=sys.stderr)
            return 2

    machine = MachineConfig(
        machine_id=1,
        machine_code="OPC_TEST",
        display_name="OPC Test",
        opc_endpoint=endpoint,
        security_policy=security_policy,
        security_mode=security_mode,
        opc_username=username,
        opc_password=password,
        enabled=True,
    )
    reader = MockOpcReader(settings) if settings.use_mock_opc else AsyncUaReader(settings)
    try:
        success, message = await reader.test_connection(machine, node_id=node_id)
        print(f"mode={'mock' if settings.use_mock_opc else 'real'}")
        status = "success" if success else "failure"
        print(f"opc_connection_status={status}")
        print(f"message={message}")
        if not success:
            return 1
        if args.browse:
            discovered = await reader.browse_nodes(machine, max_depth=args.max_depth, max_nodes=args.max_nodes)
            print(f"browse_count={len(discovered)}")
            if discovered:
                first = discovered[0]
                print(
                    "first_browse_node="
                    f"{first['browse_path']} node_id={first['opc_node_id']} class={first['node_class']} type={first['data_type']}"
                )
        return 0
    finally:
        await reader.shutdown()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run_test(args)))


if __name__ == "__main__":
    main()
