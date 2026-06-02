# Runbook

- Use `Reload Config` after machine/tag changes.
- Use `Restart Collector` only for manual recovery.
- Check `/health` for machine-level heartbeats, failures, and local buffer rows.
- Check `/collector` for recent collector commands and config version.
- If MySQL is unavailable, confirm SQLite buffer growth at `COLLECTOR_SQLITE_PATH`.
- The platform is OPC read-only. It can browse and read tags, but it does not write values back to the machine.
