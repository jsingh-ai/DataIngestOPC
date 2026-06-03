# First Machine Rollout

Use this checklist for the first real PLC or OPC UA machine. Keep the initial scope small and reversible.

## Sequence

1. Create `.env`

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\create_env.py --mode azure --interactive --output .env --overwrite
```

2. Verify DB connectivity

```cmd
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\check_db.py
```

3. Initialize schema and defaults

```cmd
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\init_db.py --migrate --seed
```

4. Start API

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform\api
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. Start collector

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform\collector
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe -m collector.main
```

6. Start frontend

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform\frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

7. Validate the OPC endpoint directly before using the dashboard

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\test_opc_connection.py --force-real --endpoint opc.tcp://10.0.0.10:4840 --security-policy Basic256Sha256 --security-mode SignAndEncrypt --username opc_reader --browse --node-id ns=2;s=Machine.Tag1
```

8. Add the machine in the dashboard.
9. Run dashboard `Test Connection`.
10. Browse tags.
11. Add only 5-10 safe read-only tags for the first rollout.
12. Reload collector config.
13. Verify `/health` shows the machine with `opc_connected=true` and `mysql_connected=true`.
14. Verify `tag_current_value` rows exist.

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\verify_first_machine_data.py --machine-code YOUR_MACHINE_CODE
```

15. Let the system run for 15 minutes.
16. Re-run the verification script.
17. Confirm there is no unexpected SQLite buffer growth.
18. Confirm there are no collector errors.

## Acceptance Criteria

- The machine stays enabled.
- `machine_collection_status` updates with a fresh heartbeat.
- `tag_current_value` contains rows for the initial tags.
- `tag_sample_minute` shows recent inserts.
- `machine_collection_status.local_buffer_rows` stays at `0` or briefly returns to `0` after flush.
- `last_error_message` remains empty or transient and understood.

## Rollback

1. Disable the machine in the dashboard.
2. Click `Reload Config`.
3. Stop the collector service.
4. Inspect the SQLite buffer file configured by `COLLECTOR_SQLITE_PATH`.

```cmd
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe -c "import sqlite3; con = sqlite3.connect(r'C:\path\to\opc_buffer.sqlite'); print(con.execute('SELECT COUNT(*) FROM buffer_samples').fetchone()[0]); con.close()"
```

5. If needed, inspect the newest buffered rows before restart.

```cmd
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe -c "import sqlite3; con = sqlite3.connect(r'C:\path\to\opc_buffer.sqlite'); rows = con.execute('SELECT buffer_id, machine_id, tag_id, created_at, last_flush_error FROM buffer_samples ORDER BY buffer_id DESC LIMIT 20').fetchall(); print(rows); con.close()"
```

6. Restart the collector after the machine is disabled or after the DB issue is corrected.
7. Confirm `verify_first_machine_data.py` no longer reports active collection for the disabled machine.
