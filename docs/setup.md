# Setup

## Local Docker MySQL

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/create_env.py --mode local --overwrite
docker compose up -d mysql
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/check_db.py
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/init_db.py --migrate --seed
```

## Azure MySQL

```bash
cd /home/jsingh/projects/DataIngestOPC/opc-platform
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/create_env.py --mode azure --interactive --output .env --overwrite
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/check_db.py
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/init_db.py --migrate --seed
```

If the Azure database has not been created and your user has privileges:

```bash
/home/jsingh/projects/DataIngestOPC/.venv/bin/python scripts/init_db.py --create-database --migrate --seed
```
