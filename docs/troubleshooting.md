# Troubleshooting

## Docker Desktop or Compose fails on Windows VM

- You do not need Docker for the Azure MySQL path.
- Ignore Docker and use `scripts\create_env.py --mode azure`, `scripts\check_db.py`, and `scripts\init_db.py` directly.
- If you do want Docker, verify Docker Desktop is running and the Linux engine is healthy.

## Cannot connect to MySQL

- Run `scripts\check_db.py`
- Verify `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- For Azure, verify firewall/private networking and `DB_SSL_CA`

## SSL error with Azure MySQL

- Set `DB_SSL_DISABLED=false`
- Set `DB_SSL_CA` to the CA certificate path
- Re-run `scripts\check_db.py`

## Migration failure

- Run `scripts\init_db.py --check-only`
- Then run `scripts\init_db.py --migrate --seed`
- If database creation is required and permitted, add `--create-database`

## OPC UA connection timeout

- Verify endpoint/port
- Increase `COLLECTOR_OPC_CONNECT_TIMEOUT_SECONDS`
- Check PLC firewall rules

## OPC UA security policy mismatch

- Verify machine `security_policy` and `security_mode`
- Set certificate/key environment variables if secure mode is required

## Machine offline

- Collector uses exponential backoff. Other machines continue collecting.
- Check `/health` for `last_error_message`

## Buffer growing

- MySQL may be down or slow
- Check `machine_collection_status.local_buffer_rows`
- Verify `scripts\check_db.py`

## Dashboard slow

- Tag and browse pages are paginated server-side
- Reduce page size from 1000 to 100 or 250 if needed
