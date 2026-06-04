# Setup

## Azure MySQL

This is the primary path for a Windows VM. It does not require Docker.

```cmd
set "REPO_ROOT=C:\Users\jsingh\Desktop\DATAINGESTOPC"
cd /d "%REPO_ROOT%"
"%REPO_ROOT%\.venv\Scripts\python.exe" scripts\create_env.py --mode azure --interactive --output .env --overwrite
"%REPO_ROOT%\.venv\Scripts\python.exe" scripts\check_db.py
"%REPO_ROOT%\.venv\Scripts\python.exe" scripts\init_db.py --migrate --seed
```

If the Azure database has not been created and your user has privileges:

```cmd
set "REPO_ROOT=C:\Users\jsingh\Desktop\DATAINGESTOPC"
cd /d "%REPO_ROOT%"
"%REPO_ROOT%\.venv\Scripts\python.exe" scripts\init_db.py --create-database --migrate --seed
```

## Optional Local Docker MySQL

Only use this if Docker Desktop works correctly on your machine.

```cmd
set "REPO_ROOT=C:\Users\jsingh\Desktop\DATAINGESTOPC"
cd /d "%REPO_ROOT%"
"%REPO_ROOT%\.venv\Scripts\python.exe" scripts\create_env.py --mode local --overwrite
docker compose up -d mysql
"%REPO_ROOT%\.venv\Scripts\python.exe" scripts\check_db.py
"%REPO_ROOT%\.venv\Scripts\python.exe" scripts\init_db.py --migrate --seed
```
