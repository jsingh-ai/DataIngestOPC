# OPC Platform

Windows-first operator guide for the OPC UA data collection platform.

Use this repo to:
- connect to OPC UA machines in read-only mode
- browse and select tags
- collect samples into Azure MySQL
- view machine health and current values in a dashboard

The default path below assumes the repo is at:

`C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform`

If your path is different, replace it in the commands.

## What You Need

- Windows Command Prompt
- Python 3.11+
- Node.js 18+
- Access to Azure MySQL

Docker is optional. Use it only if your Windows VM can run Docker Desktop correctly.

## Copy-Paste Setup

### 1) Install Python packages

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
python -m venv C:\Users\jsingh\Desktop\DataIngestOPC\.venv
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\pip.exe install -r requirements.txt
```

### 2) Create `.env` for Azure MySQL

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\create_env.py --mode azure --interactive --output .env --overwrite
```

Fill in:
- Azure MySQL host
- database name
- database user
- database password
- SSL CA path if Azure requires it
- admin username
- admin password
- `USE_MOCK_OPC=true` for a dry run, or `USE_MOCK_OPC=false` when you are ready for a real machine

### 3) Check the database

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\check_db.py
```

### 4) Create tables and seed defaults

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\init_db.py --migrate --seed
```

If the Azure database does not exist yet and your user is allowed to create it:

```cmd
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\init_db.py --create-database --migrate --seed
```

### 5) Start the API

Open a new Command Prompt window:

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform\api
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6) Start the collector

Open a second Command Prompt window:

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform\collector
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe -m collector.main
```

### 7) Start the frontend

Open a third Command Prompt window:

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform\frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

### 8) Open the dashboard

Open:

`http://127.0.0.1:5173`

Log in with the admin username and password from `.env`.

## What To Click In The Dashboard

1. Go to `Machines`
2. Click `Add Machine`
3. Enter the machine IP and OPC endpoint
4. Click `Test Connection`
5. Save the machine only after the connection succeeds
6. Click `Browse Tags`
7. Select 5 to 10 safe read-only tags
8. Add the tags
9. Click `Reload Config`
10. Watch `Health` and `Collector`

## Direct OPC Test

Use this when you want to test a machine before adding it in the dashboard:

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\test_opc_connection.py --force-real --endpoint opc.tcp://10.0.0.10:4840 --username opc_reader --node-id ns=2;s=Machine.Tag1
```

If you do not pass `--password`, the script prompts securely.

## Windows VM With Azure MySQL

This is the recommended path for a Windows VM that cannot run Docker.

Use this order:

1. `scripts\create_env.py --mode azure --interactive --output .env --overwrite`
2. `scripts\check_db.py`
3. `scripts\init_db.py --migrate --seed`
4. Start API
5. Start collector
6. Start frontend
7. Open `http://127.0.0.1:5173`
8. Add a machine
9. Test connection
10. Browse tags
11. Add a few read-only tags
12. Click `Reload Config`

## Optional Docker Path

Only use this if Docker Desktop works on the machine.

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\create_env.py --mode local --overwrite
docker compose up -d mysql
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\check_db.py
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\init_db.py --migrate --seed
```

## Collector Behavior

- The collector reads enabled machines and tags from MySQL.
- It connects to OPC UA machines in read-only mode.
- It writes samples to SQLite first.
- It flushes batches into MySQL.
- If one machine is offline, the others keep running.

## Read-Only Guarantee

This platform does not send OPC UA write requests.
It can browse and read tags only.

## Run Checks

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\run_all_checks.py --mode azure
```

If Docker works and you want to use the local container path instead:

```cmd
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\run_all_checks.py --mode local-docker
```

## Troubleshooting

- MySQL connect errors: run `scripts\check_db.py`
- Azure SSL errors: set `DB_SSL_DISABLED=false` and `DB_SSL_CA`
- Migration errors: run `scripts\init_db.py --check-only` then `--migrate --seed`
- OPC timeout: verify the endpoint and port
- Docker errors on a VM: use the Azure MySQL path instead
- Browser login `Failed to fetch`: make sure the API is running and the frontend was restarted

## More Docs

- [Setup](docs/setup.md)
- [Runbook](docs/runbook.md)
- [API](docs/api.md)
- [Collector](docs/collector.md)
- [Troubleshooting](docs/troubleshooting.md)
- [First Machine Rollout](docs/first_machine_rollout.md)
