# SIH26162 Thermal Intelligence Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL%20%2B%20PostGIS-runtime-336791?logo=postgresql&logoColor=white)](https://postgis.net/)
[![React](https://img.shields.io/badge/React%2019-TypeScript-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![MapLibre](https://img.shields.io/badge/MapLibre%20%2B%20deck.gl-geospatial-3969AC)](https://maplibre.org/)

An evidence-first decision-support platform for detecting, classifying, and monitoring industrial fires and persistent thermal sources from NASA FIRMS observations.

The platform converts individual satellite detections into stable physical source sites, evaluates each site with three independent intelligence components, combines their outputs with a deterministic alert policy, and presents the result in a live/replay geospatial command center.

> This system supports analyst decision-making. It is not life-safety-grade fire confirmation, and a satellite hotspot is not automatically an industrial fire.

![SIH26162 intelligence architecture](docs/assets/architecture.png)

## What the platform answers

| Stage | Operational question | Implementation | Main output |
| --- | --- | --- | --- |
| Source resolver | Which detections belong to the same physical source? | Frozen 750 m source definition plus incremental live assignment | Stable `site_id` or audited candidate source |
| Model A | What kind of source is it? | XGBoost A-Core using the deployed 33-feature order; optional guarded Prithvi rescue | `INDUSTRIAL`, `NONINDUSTRIAL`, or `UNKNOWN` |
| Model B | How is it behaving over time? | Deterministic temporal-state engine | `NEW`, `INTERMITTENT`, `PERSISTENT`, `DORMANT`, or `REACTIVATED` |
| Model C | Is today's activity unusual for this site? | Chronological site-specific robust anomaly engine | `NORMAL`, `ELEVATED`, `ANOMALOUS`, `CRITICAL`, or `INSUFFICIENT_HISTORY` |
| Decision engine | What action should an analyst take? | Frozen deterministic A+B+C policy | Deduplicated operational alert and reason codes |
| Command center | How is the evidence explored? | FastAPI, PostgreSQL/PostGIS, React, MapLibre, and deck.gl | Live map, replay, alerts, timelines, evidence, and raw detections |

```mermaid
flowchart LR
    FIRMS[NASA FIRMS<br/>NOAA-20 NRT] --> INGEST[Normalize and<br/>deduplicate]
    INGEST --> RESOLVE[750 m incremental<br/>source resolver]
    RESOLVE --> SITE[(PostgreSQL<br/>PostGIS)]
    WC[ESA WorldCover] --> A[Model A<br/>source identity]
    SITE --> A
    SITE --> B[Model B<br/>temporal state]
    SITE --> C[Model C<br/>site anomaly]
    HLS[HLS imagery] -. optional .-> P[Prithvi rescue]
    P -. guarded rescue only .-> A
    A --> DECIDE[Deterministic<br/>decision engine]
    B --> DECIDE
    C --> DECIDE
    DECIDE --> API[FastAPI and SSE]
    SITE --> API
    API --> UI[OSIRIS-style<br/>web command center]
```

## Runtime principles

- A hotspot is evidence, not a confirmed incident.
- The source resolver remains fixed at a 750 m neighborhood radius with `min_samples=3` semantics.
- Model A uses exactly the feature order declared in `backend/config/model_a_features.json`; the deployed artifact currently expects 33 features.
- Model B is a deterministic state engine, not a fitted ML model.
- Model C only compares a site-day with earlier completed active days. Future observations never enter a historical baseline.
- `UNKNOWN` and `INSUFFICIENT_HISTORY` are valid outputs and are never replaced merely to make the UI look complete.
- A-Core responds immediately. HLS/Prithvi is optional, asynchronous evidence for uncertain A-Core results and can never veto an A-Core probability at or above `0.885`.
- FIRMS, Earthdata, database, and model credentials stay in the backend. The browser never calls those services directly.

## Implemented capabilities

- Frozen Model A, B, and C runtime engines with regression coverage.
- Incremental source resolution, candidate accumulation, ambiguity auditing, and stable-site promotion.
- Idempotent NOAA-20 FIRMS ingestion and resumable historical backfill.
- ESA WorldCover feature retrieval with a persistent raster cache.
- PostgreSQL/PostGIS runtime schema, bootstrap loader, migrations, current model snapshots, and database snapshot tooling.
- Deterministic alerts with stable fingerprints and same-day escalation.
- FastAPI REST endpoints, live controls, scheduler telemetry, and Server-Sent Events.
- React/TypeScript command center with a MapLibre/deck.gl globe, filters, site drawer, alert rail, and leakage-safe historical replay.
- Four deterministic offline demo scenarios with checksummed replay caches and a walkthrough script.
- Optional asynchronous HLS/Prithvi imagery processing.

## Choose a setup path

| Path | Best for | Database source | Expected effort |
| --- | --- | --- | --- |
| **Fast snapshot restore** | Teammates who need the same populated database immediately | Compressed PostgreSQL dump | Minutes; recommended |
| **Clean rebuild** | Reproducibility, a new data cutoff, or a missing snapshot | Repository bootstrap data plus FIRMS backfill | Potentially hours because WorldCover and inference must be materialized |
| **Docker Compose** | Isolated deployment or CI-style testing | Empty PostgreSQL volume unless separately restored/bootstraped | Fast services, but data setup is still required |

The native Windows/PostgreSQL setup is the primary development path. Docker is optional.

## Prerequisites

Install the following before continuing:

| Requirement | Supported/recommended version | Check |
| --- | --- | --- |
| Git | Current | `git --version` |
| Python | **3.11 exactly** for the frozen runtime | `python --version` |
| Node.js | `20.19+` or `22.12+` | `node --version` |
| npm | Bundled with Node.js | `npm --version` |
| PostgreSQL | PostgreSQL with matching PostGIS installation; the current shared snapshot was produced by PostgreSQL 18.4 | `psql --version` |
| PostGIS | Installed for the local PostgreSQL server | Check with the SQL command below |

On Windows, the database scripts automatically search `C:\Program Files\PostgreSQL\<version>\bin` when PostgreSQL tools are not on `PATH`.

## 1. Clone and prepare the application

Run all backend commands from the repository root.

```powershell
git clone <repository-url> sih26162-thermal-ai
Set-Location .\sih26162-thermal-ai

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\backend\requirements.txt

Copy-Item .\.env.example .\.env

Set-Location .\frontend
npm ci
Set-Location ..
```

If PowerShell prevents virtual-environment activation, permit locally created scripts for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Virtual environments are machine-specific. Do not copy `.venv` from another computer. If its launcher points to a missing Python installation, delete only that broken `.venv`, recreate it with an installed Python 3.11 interpreter, and reinstall the requirements.

## 2. Configure the environment

Edit the root `.env` file. At minimum, configure the database URL and FIRMS key:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/sih26162
FIRMS_MAP_KEY=YOUR_NASA_FIRMS_MAP_KEY
FIRMS_PRIMARY_SOURCE=VIIRS_NOAA20_NRT
FIRMS_SECONDARY_SOURCE=VIIRS_NOAA21_NRT
FIRMS_BBOX=67,6,98,38
FIRMS_POLL_MINUTES=15
AUTO_STARTUP_CATCHUP=true
MODEL_ROOT=backend/models
MODEL_STACK_VERSION=2026-09-04-r1
ALLOWED_ORIGINS=http://localhost:3000
PRITHVI_ENABLED=false
EARTHDATA_USERNAME=
EARTHDATA_PASSWORD=
PRITHVI_DEVICE=auto
PRITHVI_ALLOW_CPU_FALLBACK=true
PRITHVI_RETRY_AFTER_MINUTES=60
HLS_CACHE_DIR=./data/cache/hls
REPLAY_ENABLED=true
REPLAY_CACHE_ENABLED=true
```

Important configuration behavior:

- `FIRMS_MAP_KEY` is required for live mode and scheduled polling. Keep it secret and never commit `.env`.
- `PRITHVI_ENABLED=false` enables core live operation without visual rescue. Model A-Core, Model B, Model C, FIRMS ingestion, alerts, and replay continue to work.
- Set `PRITHVI_ENABLED=true` only for full live operation with visit-triggered HLS/Prithvi evaluation. This additionally requires the packaged visual artifacts and NASA Earthdata credentials described below.
- `PRITHVI_DEVICE=auto` selects CUDA when available and otherwise uses CPU. CPU is supported, but the first inference is slower because the 300M encoder is loaded lazily.
- Environment changes are read at backend process startup. Restart the backend after modifying `.env`.
- If the password contains URL-reserved characters such as `@`, `:`, `/`, or `#`, URL-encode it in `DATABASE_URL`.

### Choose the required live capability

| Capability | Required settings | Behavior |
| --- | --- | --- |
| **Core live** | Current database, valid `FIRMS_MAP_KEY`, `PRITHVI_ENABLED=false` | Scheduled FIRMS ingestion and A/B/C processing run normally; uncertain Model A sites remain `UNKNOWN` without visual evaluation |
| **Full live with Prithvi** | Core live requirements, `PRITHVI_ENABLED=true`, Earthdata credentials, and all visual artifacts | Visiting an eligible live `UNKNOWN` site queues genuine HLS retrieval and guarded Prithvi evaluation |

Prithvi is optional for the platform but required for the automatic visual-rescue experience in the site drawer. It never changes a confident A-Core decision and is never launched by historical replay.

## 3A. Fast database setup from the shared snapshot

This is the recommended teammate setup. A restored PostgreSQL database is not a `.db` file inside the repository: PostgreSQL stores it in its own managed server data directory. The portable artifact is the custom-format dump plus its checksum and metadata.

The current workspace snapshot contains:

| Property | Value |
| --- | ---: |
| Database | `sih26162` |
| Data through | `2026-09-08` |
| Source sites | 118,779 |
| FIRMS detections | 1,580,275 |
| Uncompressed database size | approximately 2.82 GiB |
| Compressed dump size | approximately 250.6 MiB |
| PostgreSQL version used to export | 18.4 |

The snapshot files are intentionally not committed to Git. Share `data/database_snapshots.zip` through an appropriate large-file channel, then extract it into the repository's `data` directory:

```powershell
Expand-Archive `
  -LiteralPath .\data\database_snapshots.zip `
  -DestinationPath .\data
```

The resulting files should be:

```text
data/database_snapshots/
|-- sih26162_runtime_2026-09-08.dump
|-- sih26162_runtime_2026-09-08.dump.sha256
`-- sih26162_runtime_2026-09-08.dump.json
```

Restore into a new local database. The script securely prompts for the PostgreSQL password when `POSTGRES_PASSWORD` is not set:

```powershell
.\backend\scripts\restore_runtime_database.ps1 `
  -DumpPath .\data\database_snapshots\sih26162_runtime_2026-09-08.dump `
  -Database sih26162 `
  -Username postgres `
  -Jobs 4
```

The restore script:

1. verifies the SHA-256 sidecar;
2. creates the target database;
3. restores with parallel workers and without source ownership/ACLs;
4. verifies site count, detection count, latest activity date, and PostGIS.

If `sih26162` already exists, the safe choices are:

- restore under another name, for example `-Database sih26162_restored`, and update `DATABASE_URL`; or
- use `-Replace` only when you intentionally want the script to drop and replace the existing database.

> `-Replace` is destructive for the named target database. It does not affect other PostgreSQL databases.

Verify the restored database directly:

```powershell
psql -U postgres -d sih26162 -c "SELECT PostGIS_Version();"
psql -U postgres -d sih26162 -c "SELECT count(*) AS sites FROM source_sites;"
psql -U postgres -d sih26162 -c "SELECT count(*) AS detections FROM firms_detections;"
psql -U postgres -d sih26162 -c "SELECT max(acq_date) AS data_through FROM site_daily_activity;"
```

## 3B. Clean database rebuild from repository data

Use this path when a compatible snapshot is unavailable or when you need to backfill through a newer date. It creates the database, initializes ORM tables, applies the idempotent PostGIS migration, loads the authoritative 2025 bootstrap data, resumes the NOAA-20 backfill, materializes A/B/C, verifies readiness, and writes the alert-burden audit.

```powershell
.\backend\scripts\setup_local_runtime.ps1 `
  -Database sih26162 `
  -Username postgres `
  -DataThrough 2026-09-08 `
  -PythonExe .\.venv\Scripts\python.exe
```

The script prompts for the PostgreSQL password and FIRMS key if they are not already available as `POSTGRES_PASSWORD` and `FIRMS_MAP_KEY`.

If a rebuild or WorldCover download is interrupted, continue the same database and cached work instead of starting over:

```powershell
.\backend\scripts\setup_local_runtime.ps1 `
  -Database sih26162 `
  -Username postgres `
  -DataThrough 2026-09-08 `
  -PythonExe .\.venv\Scripts\python.exe `
  -Resume
```

Use a current `-DataThrough YYYY-MM-DD` value before enabling live mode. Use `-Replace` only when intentionally discarding and rebuilding the named database.

### What each database asset is for

```mermaid
flowchart TD
    BOOT[data/bootstrap<br/>tracked frozen inputs] --> LOADER[bootstrap_db.py]
    MIG[backend/migrations<br/>schema evolution] --> DB[(Local PostgreSQL<br/>PostGIS runtime)]
    LOADER --> DB
    FIRMS[NASA FIRMS backfill<br/>and live polling] --> DB
    DB --> DUMP[pg_dump snapshot<br/>fast teammate transfer]
    DUMP --> RESTORE[restore script]
    RESTORE --> TEAM[(Teammate's local<br/>PostgreSQL runtime)]
    CACHE[data/cache<br/>WorldCover, HLS, replay] -. reusable downloads .-> LOADER
```

| Location | Purpose |
| --- | --- |
| `data/bootstrap/` | Frozen source sites, 2025 detections/features, daily history, and regression inputs used to build a database from scratch |
| `backend/migrations/` | Idempotent schema changes; migrations define structure but do not contain the large operational dataset |
| PostgreSQL server data directory | The active database's physical storage, managed exclusively by PostgreSQL; never copy or edit its internal files manually |
| `data/database_snapshots/` | Portable `pg_dump` exports for fast transfer and restore |
| `data/cache/` | Reusable downloaded/derived WorldCover, HLS, and replay caches; not the authoritative relational database |
| `data/demo/replay/` | Small, tracked, checksummed offline demonstration snapshots |

## 4. Start the application

Open two terminals at the repository root.

Terminal 1 - backend:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

For a stable live prototype run, omit `--reload` so source-file changes cannot interrupt an active FIRMS or HLS task:

```powershell
.\.venv\Scripts\python.exe -u -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 - frontend:

```powershell
Set-Location .\frontend
npm run dev
```

Open:

- Command center: [http://localhost:3000](http://localhost:3000)
- Backend health: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)
- Swagger API explorer: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

On backend startup, the application validates model/config checksums, required database tables and columns, the active model versions, the common A/B/C snapshot, data freshness, and FIRMS credentials. The scheduler starts only after that preflight permits live operation.

## 5. Configure full live HLS/Prithvi evaluation

Skip this section when core live operation without Prithvi is sufficient.

### 5.1 Verify the packaged visual artifacts

Full live Prithvi requires these exact repository files:

```text
backend/models/prithvi/Prithvi_EO_V2_300M.pt
backend/models/prithvi/config.json
backend/models/prithvi/prithvi_mae.py
backend/models/MODEL_A_PRITHVI_FINAL.joblib
backend/config/source/prithvi_final_config.json
```

Their SHA-256 values must also agree with `SHA256SUMS.txt` and `backend/config/active_stack_manifest.json`. Do not retrain, rename, or replace these artifacts during setup.

### 5.2 Add backend-only Earthdata configuration

Create a NASA Earthdata Login account with access to HLS, then set the following values in the root `.env`:

```dotenv
PRITHVI_ENABLED=true
EARTHDATA_USERNAME=YOUR_EARTHDATA_USERNAME
EARTHDATA_PASSWORD=YOUR_EARTHDATA_PASSWORD
PRITHVI_DEVICE=auto
PRITHVI_ALLOW_CPU_FALLBACK=true
PRITHVI_RETRY_AFTER_MINUTES=60
HLS_CACHE_DIR=./data/cache/hls
```

Never put Earthdata credentials in frontend environment files, React code, screenshots, or Git. The browser communicates only with FastAPI; Earthdata authentication and imagery retrieval remain server-side.

Restart the backend after saving `.env`. No separate scheduler or Prithvi-worker command is required. When stack readiness permits live operation, backend startup automatically starts both APScheduler and the asynchronous Prithvi worker.

### 5.3 Verify live readiness and workers

```powershell
$health = Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
$live = Invoke-RestMethod http://127.0.0.1:8000/api/v1/live/status

$health
$live.scheduler
$live.prithvi_queue
```

Expected state for full live operation:

```text
health.status                  READY
health.database                connected
live.scheduler.is_running      true
live.prithvi_queue.worker_running true
```

`DEGRADED_PRITHVI_UNAVAILABLE` still permits core live operation, but visit-triggered visual evaluation will not complete until the reported local artifact/runtime issue is corrected. Local readiness validates the packaged Prithvi runtime; the Earthdata login itself is exercised when the first HLS scene is requested.

### 5.4 What happens when an unknown site is opened

```mermaid
flowchart LR
    OPEN[Open live UNKNOWN site] --> BAND{A-Core in<br/>0.405-0.885 band?}
    BAND -- No --> KEEP[Keep A-Core decision]
    BAND -- Yes --> QUEUE[Queue HLS/Prithvi]
    QUEUE --> HLS[Retrieve cloud-screened<br/>HLS patch]
    HLS --> SCORE[Prithvi probability]
    SCORE --> RESCUE{Score >= 0.965?}
    RESCUE -- Yes --> INDUSTRIAL[UNKNOWN to INDUSTRIAL<br/>guarded rescue]
    RESCUE -- No --> UNKNOWN[Remain UNKNOWN<br/>show visual score]
```

The drawer displays `PENDING` and refreshes from the persisted server result. Closing the drawer does not cancel processing. Successful output is stored in PostgreSQL and the compact HLS patch is cached under `HLS_CACHE_DIR`; reopening the site reuses that evidence. Cloud-rejected or unavailable imagery remains explicitly unavailable—no score is fabricated.

HLS search and first-time CPU inference can take tens of seconds depending on Earthdata latency and hardware. Retrieval checks the small cloud mask first, stops at the first valid scene, removes full GeoTIFF staging files, and retains only the compact site patch. Later evaluations in the same backend process avoid reloading the Prithvi encoder.

## 6. Verify the installation

Run the backend and frontend checks before handing off a setup:

```powershell
# Backend regression suite
.\.venv\Scripts\python.exe -m pytest .\backend\tests

# Runtime artifact and database readiness
.\.venv\Scripts\python.exe .\backend\scripts\verify_bootstrap_artifacts.py

# Offline demo bundle integrity
.\.venv\Scripts\python.exe .\backend\scripts\build_demo_cache.py --verify-only

# Frontend static checks and production build
Set-Location .\frontend
npm run lint
npm run build
Set-Location ..
```

With both services running, inspect runtime state:

```powershell
curl.exe http://127.0.0.1:8000/api/v1/health
curl.exe http://127.0.0.1:8000/api/v1/stats
curl.exe http://127.0.0.1:8000/api/v1/live/status
curl.exe http://127.0.0.1:8000/api/v1/demo/status
```

A healthy live stack reports `READY`, or `DEGRADED_PRITHVI_UNAVAILABLE` when the optional Prithvi branch is enabled but unavailable. Both statuses allow the core live pipeline to run.

## Live ingestion and scheduling

When readiness passes, backend startup automatically enables:

- NOAA-20 NRT polling at `FIRMS_POLL_MINUTES` (15 minutes by default);
- incremental source assignment and touched-site A/B/C refresh;
- daily global Model B recalculation at 00:05 UTC;
- the asynchronous Prithvi queue when configured; and
- SSE alert delivery to the frontend.

Trigger one immediate live poll from Swagger or PowerShell:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/live/trigger-poll
```

Synthetic hotspot injection is disabled by default. It is available only when `ALLOW_SIMULATION=true`, and it must remain a clearly identified demonstration feature.

## Historical replay and offline demo

Replay mode reconstructs Model B at the selected cutoff and uses chronological Model C outputs without leaking current state backward in time. The repository also contains four network-independent judging scenarios:

- industrial critical anomaly;
- industrial reactivation after dormancy;
- unknown critical analyst review; and
- nonindustrial anomaly contrast.

Verify the cached bundle and print the walkthrough:

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\build_demo_cache.py --verify-only
.\.venv\Scripts\python.exe .\backend\scripts\demo_walkthrough.py
```

The corresponding APIs are:

```text
GET /api/v1/demo/status
GET /api/v1/demo/scenarios
GET /api/v1/demo/scenarios/{scenario_id}/snapshot?date=YYYY-MM-DD
GET /api/v1/replay?date=YYYY-MM-DD
```

## Share an updated database with teammates

Exporting produces three files: a compressed PostgreSQL dump, SHA-256 checksum, and JSON metadata record.

```powershell
.\backend\scripts\export_runtime_database.ps1 `
  -Database sih26162 `
  -Username postgres
```

The script prints the exact output paths under `data/database_snapshots/`. Share all three files together. For a single transfer artifact, package the directory after export:

```powershell
$snapshotArchive = ".\data\database_snapshots_$(Get-Date -Format 'yyyyMMdd_HHmmss').zip"
Compress-Archive `
  -Path .\data\database_snapshots `
  -DestinationPath $snapshotArchive `
  -CompressionLevel Optimal
```

Database dumps are large runtime artifacts and should be distributed outside ordinary Git history. Recipients restore them with `backend/scripts/restore_runtime_database.ps1` as described above.
.\.venv\Scripts\python.exe  .\backend\scripts\backfill_firms_2026.py `                                                                
>>   --start-date 2026-01-01 `                                          
>>   --end-date 2026-09-11 `
>>   --update-db
## Docker Compose (optional)

Docker Compose starts PostGIS, the FastAPI container, and the production frontend:

```powershell
Copy-Item .\.env.example .\.env
docker compose up --build
```

This creates a persistent Docker volume named `postgis_data`, but a newly created volume does not automatically contain the populated runtime database. Restore a snapshot or run the bootstrap/backfill workflow before expecting live data. Keep secrets in `.env`; do not place them in `docker-compose.yml` or frontend source.

## Troubleshooting

### The frontend says live mode is blocked

Check `GET /api/v1/health`. The backend intentionally fails closed:

| Health status | Meaning | Resolution |
| --- | --- | --- |
| `DATABASE_NOT_READY` | Database connection, required tables, or required columns are missing | Confirm `DATABASE_URL`; restore a snapshot or run the setup/migration workflow |
| `STALE_BACKFILL` | No common A/B/C snapshot exists through the operational date | Resume `setup_local_runtime.ps1` with a current `-DataThrough` date |
| `MODEL_ARTIFACT_MISMATCH` | A required file, manifest entry, checksum, active model version, or feature contract disagrees | Restore the repository artifacts; do not retrain or edit frozen thresholds |
| `FIRMS_CREDENTIALS_MISSING` | `FIRMS_MAP_KEY` is empty | Add the backend-only key to `.env` and restart the API |
| `DEGRADED_PRITHVI_UNAVAILABLE` | Optional Prithvi evidence could not start | Core live mode remains available; fix Prithvi only if imagery rescue is needed |

### Python reports "No Python at ..."

The `.venv` launcher references a Python installation that no longer exists. Recreate the virtual environment with Python 3.11 and reinstall `backend/requirements.txt`. Do not point the project at pgAdmin's bundled Python.

### PostgreSQL tools are not found

Add the PostgreSQL `bin` directory to `PATH`, or confirm PostgreSQL is installed under `C:\Program Files\PostgreSQL\<version>`. The provided PowerShell scripts search that location automatically.

### PostGIS or PROJ reports mixed-installation warnings

Keep PostgreSQL/PostGIS tools and the Python GIS stack isolated. Do not set a global `PROJ_LIB`/`PROJ_DATA` to PostgreSQL's PostGIS `proj.db` while running Rasterio from the virtual environment. Restart the terminal after correcting those variables.

### Rasterio logs `boto3 not available, falling back to a DummySession`

This is informational when accessing public HTTP/COG resources without an AWS-authenticated session. It is not a failed WorldCover download by itself.

### A WorldCover TIFF tile has a read error

An interrupted download can leave a truncated cached tile. Stop the worker, remove only the exact corrupt tile named in the error, and resume the setup/backfill so that tile is downloaded again. Never delete the whole cache unless a complete redownload is intended.

### The database is not visible as a file in the repository

That is expected. PostgreSQL owns the active database inside its configured server data directory. Use `pg_dump`, `export_runtime_database.ps1`, and `restore_runtime_database.ps1`; never copy PostgreSQL's internal `base/` files between machines.

## Repository map

```text
sih26162-thermal-ai/
|-- backend/
|   |-- app/
|   |   |-- api/v1/            FastAPI routes, live controls, replay, and SSE
|   |   |-- db/                SQLAlchemy models and database sessions
|   |   |-- engines/           Source resolver and frozen A/B/C/decision engines
|   |   `-- services/          FIRMS, WorldCover, HLS, scheduler, replay, and queues
|   |-- config/                Machine-readable frozen thresholds and contracts
|   |-- migrations/            Idempotent PostgreSQL/PostGIS schema migration
|   |-- models/                Serialized A-Core, Prithvi head, Model C, and optional weights
|   |-- scripts/               Bootstrap, backfill, readiness, demo, and snapshot utilities
|   `-- tests/                 Unit, integration, and frozen regression tests
|-- data/
|   |-- bootstrap/             Tracked authoritative bootstrap inputs
|   |-- cache/                 Downloaded/derived caches (gitignored)
|   |-- database_snapshots/    Portable PostgreSQL dumps (gitignored)
|   |-- demo/replay/           Tracked offline demo cache
|   `-- evidence/              Facility and contextual evidence inputs
|-- docs/                      Research decisions and implementation contracts
|-- frontend/                  React 19, TypeScript, Vite, MapLibre, and deck.gl
|-- .env.example               Safe environment template
|-- docker-compose.yml         Optional container deployment
|-- manifest.json              Packaged artifact inventory
`-- SHA256SUMS.txt              Frozen artifact checksums
```

## Key API routes

| Route | Purpose |
| --- | --- |
| `GET /api/v1/health` | Readiness, database, PostGIS, and active model versions |
| `GET /api/v1/stats` | National runtime totals and A/B/C distributions |
| `GET /api/v1/sites` | Viewport-filtered site GeoJSON |
| `GET /api/v1/sites/{site_id}` | Full site intelligence summary |
| `GET /api/v1/sites/{site_id}/timeline` | Daily thermal and model timeline |
| `GET /api/v1/sites/{site_id}/detections` | Raw normalized FIRMS observations |
| `GET /api/v1/sites/{site_id}/evidence` | Facility and contextual evidence |
| `GET /api/v1/sites/{site_id}/imagery` | Cached HLS/Prithvi evidence status |
| `GET /api/v1/alerts` | Operational alert feed |
| `POST /api/v1/alerts/{alert_id}/ack` | Analyst acknowledgement |
| `GET /api/v1/replay` | Leakage-safe historical reconstruction |
| `GET /api/v1/stream/alerts` | Live SSE alert stream |
| `GET /api/v1/live/status` | Scheduler and queue telemetry |
| `POST /api/v1/live/trigger-poll` | On-demand FIRMS polling cycle |

## Scientific and implementation documentation

The runtime is governed by the frozen configuration files under `backend/config/`. The research documents explain the decisions and validation boundaries:

- [System overview](docs/00_overview.md)
- [Data and ground truth](docs/01_data_and_ground_truth.md)
- [Model A](docs/02_model_a.md)
- [Model B](docs/03_model_b.md)
- [Model C](docs/04_model_c.md)
- [Validation claims](docs/05_validation_claims.md)
- [Decision engine](docs/06_decision_engine.md)
- [FIRMS and imagery integration](docs/07_firms_integration.md)
- [Backend and database](docs/08_backend_and_db.md)
- [Frontend](docs/09_frontend.md)
- [Deployment and operations](docs/10_deployment_ops.md)
- [Testing roadmap](docs/11_testing_roadmap.md)
- [Artifact and environment contract](docs/13_artifacts_env_contract.md)

Where archived prose differs from the packaged runtime, use the checked-in machine-readable config and active artifact manifest. Do not silently retrain models or redesign frozen logic.

## License and attribution

Developed for Smart India Hackathon problem statement SIH26162, *AI-Based Detection and Classification of Industrial Fires and Persistent Thermal Sources*.

Retain applicable attribution and licensing for NASA FIRMS, ESA WorldCover, HLS/Earthdata, IBM/NASA Prithvi-EO, OpenStreetMap, and external facility/evidence datasets when redistributing data or model artifacts.
