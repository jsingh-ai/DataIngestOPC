from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(Path("/home/jsingh/projects/DataIngestOPC/.venv/bin/python"))


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def main() -> None:
    run(["docker", "compose", "up", "-d", "mysql"], cwd=ROOT)
    run([PYTHON, "scripts/create_env.py", "--mode", "local", "--overwrite"], cwd=ROOT)
    run([PYTHON, "scripts/check_db.py"], cwd=ROOT)
    run([PYTHON, "scripts/init_db.py", "--migrate", "--seed"], cwd=ROOT)
    run([PYTHON, "-m", "pytest", "api/tests", "collector/tests"], cwd=ROOT)
    run([PYTHON, "-m", "ruff", "check", "api", "collector", "scripts"], cwd=ROOT)
    run([PYTHON, "-m", "mypy", "api/app", "collector/collector", "scripts"], cwd=ROOT)
    frontend = ROOT / "frontend"
    run(["npm", "run", "lint"], cwd=frontend)
    run(["npm", "run", "typecheck"], cwd=frontend)
    run(["npm", "run", "build"], cwd=frontend)
    print("Running mock soak in buffer-only mode. SQLite growth is expected here because no MySQL flush is attempted.")
    run([PYTHON, "scripts/soak_collector_mock.py", "--duration-seconds", "5", "--accelerated", "--buffer-only"], cwd=ROOT)
    print("Running end-to-end mock acceptance. This covers DB writes and asserts the SQLite buffer drains when MySQL is reachable.")
    run([PYTHON, "scripts/e2e_mock_acceptance.py"], cwd=ROOT)
    print("All checks passed")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
