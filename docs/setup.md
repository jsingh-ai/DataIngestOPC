# Setup

## Local Docker MySQL

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\create_env.py --mode local --overwrite
docker compose up -d mysql
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\check_db.py
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\init_db.py --migrate --seed
```

## Azure MySQL

```cmd
cd /d C:\Users\jsingh\Desktop\DataIngestOPC\opc-platform
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\create_env.py --mode azure --interactive --output .env --overwrite
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\check_db.py
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\init_db.py --migrate --seed
```

If the Azure database has not been created and your user has privileges:

```cmd
C:\Users\jsingh\Desktop\DataIngestOPC\.venv\Scripts\python.exe scripts\init_db.py --create-database --migrate --seed
```
