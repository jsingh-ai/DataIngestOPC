# OPC Platform

Production-oriented OPC UA data collection platform for collecting machine data into Azure MySQL and serving a fast admin dashboard for machine, tag, health, and collector operations.

In local development, the frontend talks to the API through the Vite `/api` proxy. The browser opens the frontend on port `5173`, and Vite forwards API requests to the backend on port `8000`.

## Simple Explanation

If you are running this for the first time, think of it in this order:

1. You log into the dashboard.
2. You add a machine by entering its IP address, port, and OPC UA endpoint.
3. You test the connection to that machine.
4. You browse tags from that machine only when you click `Browse Tags`.
5. You choose 5 to 10 safe read-only tags for the first machine.
6. You save those tags and click `Reload Config`.
7. The collector reads the enabled tags, writes samples to SQLite first, and then flushes them to MySQL.
8. The health pages show whether the machine is online, whether MySQL is reachable, and whether samples are flowing.
9. This platform is read-only to the OPC machine. It browses and reads tags, but it does not write values back to the PLC.

Where you type the machine IP:
- In the dashboard at `Machines -> Add Machine`
- Put the machine IP in `IP Address`
- The app builds the OPC endpoint from the IP and port, or you can edit the endpoint directly
- Example endpoint: `opc.tcp://10.0.0.10:4840`

How login works:
- The dashboard login uses the admin username and password from `.env`
- For local development, `scripts/create_env.py --mode local` creates a working admin login
- For Azure or production, you set the admin username and password yourself in `.env`

What the backend does:
- FastAPI stores machines, tags, browse cache, health, and collector commands
- It talks to Azure MySQL
- It does not browse PLCs automatically on page load

What the frontend does:
- React gives you the dashboard
- You use it to add machines, browse tags, enable or disable tags, and reload the collector
- The frontend never connects to the PLC directly

What the collector does:
- The collector reads enabled machines and enabled tags from MySQL
- It connects to the OPC UA machines
- It samples tags on their scan profile
- It writes each sample to SQLite first
- It flushes batches from SQLite into MySQL
- It keeps running even if one machine is offline

## What Is Included

- `frontend/`: React + TypeScript + Vite dashboard
- `api/`: FastAPI control plane and read APIs
- `collector/`: long-running async collector with a local SQLite durable buffer
- `scripts/`: environment, DB bootstrap, seed, validation, and soak scripts
- `docs/`: setup, runbook, rollout, troubleshooting, and deployment notes
- `deploy/`: systemd and nginx templates

## Architecture

- Dashboard -> FastAPI API -> Azure MySQL
- Collector -> Azure MySQL
- Collector -> OPC UA machines
- Dashboard does not talk to PLCs directly
- API and collector are separate services

## What The Platform Does

- Add and edit OPC UA machines
- Test OPC UA connections
- Browse OPC UA tags on demand
- Cache browse results in MySQL
- Add selected tags from browse cache
- Enable or disable machines and tags
- Edit tag names, folder paths, and scan profiles
- Reload collector config without restarting the API
- Restart collector cleanly when needed
- Track current values and machine/tag health
- Buffer samples locally in SQLite before MySQL flush
- Read OPC UA tags only. There is no OPC write path in the collector or API.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose for local MySQL
- Access to Azure MySQL for production

Install the Python dependencies into a fresh virtualenv with:

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Local Development Quick Start

Use this order:

1. Create `.env`
2. Start local MySQL
3. Check DB connectivity
4. Run migrations and seed defaults
5. Start API
6. Start collector
7. Start frontend

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/create_env.py --mode local --overwrite
docker compose up -d mysql
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/check_db.py
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/init_db.py --migrate --seed
```

Start the services in separate terminals:

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform/api
/home/jsingh/projects/DataIngestOPC/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform/collector
/home/jsingh/projects/DataIngestOPC/.venv/bin/python -m collector.main
```

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform/frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

Open the dashboard in your browser and log in with the admin credentials you set in `.env`.

If you want the exact operator checklist, use the simple sequence above and then follow the machine rollout doc.

For local development, `VITE_API_BASE_URL` is optional. If it is not set, the frontend uses the Vite `/api` proxy. If you change it, restart the frontend dev server.

## Local Docker Full Stack

If you want to run the API, collector, frontend, and MySQL from Docker:

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform
docker compose up --build
```

## Azure MySQL Setup

Use this sequence for a real Azure MySQL environment:

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/create_env.py --mode azure --interactive --output .env --overwrite
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/check_db.py
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/init_db.py --migrate --seed
```

If your MySQL user is allowed to create the database:

```bash
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/init_db.py --create-database --migrate --seed
```

## Real OPC UA Setup

1. Set `USE_MOCK_OPC=false` in `.env`.
2. If the PLC requires OPC UA security, set:
   - `OPC_CLIENT_CERTIFICATE_PATH`
   - `OPC_CLIENT_PRIVATE_KEY_PATH`
   - `OPC_CLIENT_PRIVATE_KEY_PASSWORD` if needed
   - `OPC_SERVER_CERTIFICATE_PATH` if certificate pinning is required
3. Start the API and collector.
4. Add a machine in the dashboard.
5. Run `Test Connection`.
6. Run `Browse Tags`.
7. Add selected tags from cache.
8. Keep the first rollout small: 5-10 read-only tags.
9. Click `Reload Config`.
10. Watch `/health` and `/collector`.

For direct validation without the dashboard:

```bash
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/test_opc_connection.py \
  --force-real \
  --endpoint opc.tcp://10.0.0.10:4840 \
  --username opc_reader \
  --node-id 'ns=2;s=Machine.Tag1'
```

If you do not pass `--password`, the script prompts securely with `getpass`.

You can also use environment variables:

```bash
export OPC_TEST_ENDPOINT='opc.tcp://10.0.0.10:4840'
export OPC_TEST_USERNAME='opc_reader'
export OPC_TEST_PASSWORD='replace-me'
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/test_opc_connection.py --force-real --browse
```

Avoid `--password` unless necessary because it may appear in shell history.

## First Machine Rollout

Use [docs/first_machine_rollout.md](/home/jsingh/projects/DataIngestOPC/opc-platform/docs/first_machine_rollout.md) for the real go-live checklist.

## Collector Operations

- `Reload Config`: normal path after machine or tag edits. The collector reloads published config without an API restart.
- `Restart Collector`: manual recovery path. The collector stops sampling, flushes what it can, closes sessions, and exits so Docker or systemd can restart it.
- Local buffer path: `COLLECTOR_SQLITE_PATH`
- Buffer health signal: `machine_collection_status.local_buffer_rows`
- If MySQL is unavailable, samples continue to land in SQLite and flush later.

## Validation and Checks

Run the full local gate:

```bash
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/run_all_checks.py
```

Useful standalone scripts:

- `scripts/test_opc_connection.py`
- `scripts/verify_first_machine_data.py`
- `scripts/soak_collector_mock.py`
- `scripts/e2e_mock_acceptance.py`
- `scripts/check_db.py`
- `scripts/init_db.py`

## Deployment Templates

- Systemd API example: [deploy/systemd/opc-api.service.example](/home/jsingh/projects/DataIngestOPC/opc-platform/deploy/systemd/opc-api.service.example)
- Systemd collector example: [deploy/systemd/opc-collector.service.example](/home/jsingh/projects/DataIngestOPC/opc-platform/deploy/systemd/opc-collector.service.example)
- Nginx example: [deploy/nginx/opc-platform.conf.example](/home/jsingh/projects/DataIngestOPC/opc-platform/deploy/nginx/opc-platform.conf.example)

## Security Notes

- Do not commit `.env`.
- Use a strong admin password.
- Keep `PASSWORD_ENCRYPTION_KEY` secret.
- Use read-only OPC users where possible.
- Prefer Azure private networking and restricted firewall rules.

## Troubleshooting

- SQL connection problems and categorized errors: see [docs/troubleshooting.md](/home/jsingh/projects/DataIngestOPC/opc-platform/docs/troubleshooting.md)
- Azure SSL issues: verify `DB_SSL_DISABLED=false` and `DB_SSL_CA`. If you do not provide an explicit CA, the app falls back to the `certifi` CA bundle, but some Azure environments still require a vendor-specific CA bundle.
- Database does not exist: create it first or use `--create-database` if permitted
- OPC security mismatch: verify the machine settings match the PLC policy and mode
- Buffer growth during MySQL outage is expected until MySQL recovers

## Docs

- [Setup](/home/jsingh/projects/DataIngestOPC/opc-platform/docs/setup.md)
- [Runbook](/home/jsingh/projects/DataIngestOPC/opc-platform/docs/runbook.md)
- [API](/home/jsingh/projects/DataIngestOPC/opc-platform/docs/api.md)
- [Collector](/home/jsingh/projects/DataIngestOPC/opc-platform/docs/collector.md)
- [Troubleshooting](/home/jsingh/projects/DataIngestOPC/opc-platform/docs/troubleshooting.md)
- [First Machine Rollout](/home/jsingh/projects/DataIngestOPC/opc-platform/docs/first_machine_rollout.md)
