# SIH26162: AI-Based Detection and Classification of Industrial Fires & Persistent Thermal Sources

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL_18-PostGIS-336791.svg?logo=postgresql&logoColor=white)](https://postgis.net)
[![React](https://img.shields.io/badge/React_19-TypeScript-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![MapLibre GL](https://img.shields.io/badge/MapLibre_GL_v5-3D_Globe-3969EC.svg?logo=mapbox&logoColor=white)](https://maplibre.org)
[![Tests](https://img.shields.io/badge/pytest-61%2F61_passing-brightgreen.svg?logo=pytest&logoColor=white)](backend/tests/)

> **Real-Time Satellite Thermal Intelligence and Early-Warning Command Center** built for the Smart India Hackathon (SIH26162).  
> Transforms raw NASA FIRMS satellite thermal anomaly triggers into stable, physical industrial sites, classifies source identity, tracks operational states, detects site-specific thermal anomalies, and provides mission-critical early warning alerts.

---

## 🛰️ Problem Statement & Why Raw Hotspots Are Not Enough

NASA FIRMS (VIIRS / MODIS) provides near-real-time active-fire thermal detections from space. However, in an operational industrial safety environment:
1. **A raw satellite hotspot is NOT a confirmed fire**: It can be a regular flaring flare stack, a cement rotary kiln, a blast furnace, seasonal agricultural crop burning, or a forest wildfire.
2. **FIRMS type codes are not ground truth**: Type 2 simply designates static land anomalies, not validated industrial plants.
3. **Absence of nearby industry on OpenStreetMap does not mean wildfire**: Forcing non-industrial labels based on map proximity causes severe false negatives.
4. **Abnormality is site-specific**: A $50\,\text{MW}$ thermal signature might be everyday routine operation for Jamnagar Refinery, but catastrophic for a small chemical processing unit.

SIH26162 solves this through a **source-centric, 3-model independent intelligence architecture**.

---

## 🧠 The 3-Model Independent Intelligence Stack

```
   Raw VIIRS Hotspots (NOAA-20 / NOAA-21)
                  │
                  ▼
      ┌───────────────────────┐
      │  750m Source Resolver │  ──▶ Groups hotspots into persistent physical sites
      └───────────────────────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
 ┌──────────┐ ┌──────────┐ ┌──────────┐
 │ Model A  │ │ Model B  │ │ Model C  │
 │ Identity │ │ State    │ │ Anomaly  │
 └──────────┘ └──────────┘ └──────────┘
       │          │          │
       └──────────┼──────────┘
                  ▼
     ┌────────────────────────┐
     │ Deterministic Decision │  ──▶ Operational Alerts & Same-Day Escalation
     │      Alert Engine      │      (10 Official Actionable Alert Types)
     └────────────────────────┘
                  │
                  ▼
 ┌────────────────────────────────────┐
 │ OSIRIS-Style 3D Web Command Center │  ──▶ Live Globe, Replay Scrubber, Deep Drawer
 └────────────────────────────────────┘
```

| Component | Core Question | Underlying Engine | Output States |
| :--- | :--- | :--- | :--- |
| **Source Resolver** | Which detections belong to the same facility? | $750\,\text{m}$ Haversine DBSCAN (batch) + Incremental Spatial BallTree (live) | Stable `site_id` |
| **Model A (A-Core)** | What is this physical source? | Supervised XGBoost pipeline ($33$ physical features: Thermal, Recurrence, Spatial, ESA Land-Cover) + optional guarded **IBM/NASA Prithvi-EO-2.0** visual rescue | `INDUSTRIAL`<br>`NONINDUSTRIAL`<br>`UNKNOWN` |
| **Model B** | How is the site behaving over time? | Deterministic temporal state machine (evaluates $N_{30}, N_{90}, N_{365}$, recurrence intervals, dormancy) | `PERSISTENT`<br>`REACTIVATED`<br>`INTERMITTENT`<br>`NEW`<br>`DORMANT` |
| **Model C (V3)** | Is the current site-day abnormal for **this specific site**? | Unsupervised site-specific time-series baseline ($>5$ active days cold-start, median/MAD statistics, 4-group calibration) | `CRITICAL`<br>`ANOMALOUS`<br>`ELEVATED`<br>`NORMAL`<br>`INSUFFICIENT_HISTORY` |
| **Decision Engine** | What operational action is required? | Deterministic A+B+C fusion matrix with SHA-256 fingerprinting and incident escalation | 10 Operational Alert Types |

---

## 📊 Completed Implementation Progress (Phases 0–6)

- [x] **Phase 0: Freeze Packaging & Workspace Bootstrap**: Verified model artifacts, 33-feature pipeline integrity, Prithvi-EO-2.0 foundation model weights, and generated SHA-256 manifest.
- [x] **Phase 1: Intelligence Engines**: Implemented `source_resolver.py`, `feature_builder.py`, `model_a.py`, `model_b.py`, and `model_c.py` with 100% frozen count reproduction.
- [x] **Phase 2: Live FIRMS Ingestion & 2026 Backfill**: NASA FIRMS Area API client with idempotent SHA-256 deduplication and historical backfill script.
- [x] **Phase 3: Decision & Alert Engine**: 10 operational alert types, deterministic fingerprinting, same-day escalation, and frozen `decision_engine.json`.
- [x] **Phase 4: PostgreSQL 18 / PostGIS Database**: Bootstrapped all **79,365 physical sites**, **297,348 daily activities**, **6,294 facility evidence records** (GEM, GFMR, ICAR, FSI), and **948 alerts**.
- [x] **Phase 5: Normalized FastAPI Endpoints**: Built 18 REST endpoints and real-time Server-Sent Events (SSE) alert stream. All 61 backend tests pass.
- [x] **Phase 6: OSIRIS 3D Web Command Center**: MapLibre GL JS v5 photorealistic 3D Earth globe with keyless ESRI World Imagery, satellite orbital tracks, 1,800+ orbiting satellites, unclustered thermal points with bold black rings and glowing semantic cores, site drawer, filter rail, and replay scrubber.

---

## 🛠️ Tech Stack

* **Backend & Intelligence**:
  * Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 18, PostGIS, Uvicorn
  * XGBoost, Scikit-Learn, PyTorch, Prithvi-EO-2.0 (Foundation Model), Shapely, PyProj, PyArrow
* **Frontend**:
  * React 19, TypeScript, Vite, Tailwind CSS v4
  * MapLibre GL JS v5 (3D Spherical Earth Globe), Deck.gl v9, Lucide React
  * Zero external map API keys required (uses keyless ESRI World Imagery & Dark Canvas)

---

## 🚀 Quick Start Guide (Running Locally)

### 1. Prerequisites
* **Python 3.11+** installed
* **Node.js 20+** installed
* **PostgreSQL 18** with **PostGIS** extension running locally on port 5432 (database: `sih26162`)

### 2. Backend Setup
```bash
# 1. Activate virtual environment
.\.venv\Scripts\activate

# 2. Install dependencies (if not already installed)
pip install -r backend/requirements.txt

# 3. Verify backend test suite (all 61 tests must pass)
pytest backend/tests

# 4. Start the FastAPI backend server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
* Backend Health Check: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)
* Interactive Swagger API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Frontend Setup
```bash
# Open a new terminal in the frontend directory
cd frontend

# Install packages
npm install

# Start Vite development server
npm run dev
```
* Open your browser and navigate to: **[http://localhost:3000](http://localhost:3000)**

---

## 🧭 Operational Features & User Guide

### 1. Interactive 3D Satellite Earth Globe
* **Photorealistic Globe**: Earth in space with real-world polar satellite orbital tracks (NOAA-20, NOAA-21, Suomi-NPP, Sentinel-2, Landsat-9) and 1,800+ LEO constellation satellites.
* **Thermal Markers**: Hotspots styled matching the OSIRIS aesthetic — bold black outer rings (`#000000`) with glowing semantic cores:
  * 🟡 **Amber**: Industrial facilities (Refineries, steel plants, power stations)
  * 🟢 **Green**: Non-industrial combustion (Crop stubble, forest wildfires)
  * 🟣 **Indigo**: Unknown / analyst review required
  * 🔴 **Red Pulse**: Thermal escalation / critical anomalies

### 2. Site Intelligence Drawer
* Click any cluster or hotspot marker to slide out the detailed site intelligence drawer.
* Inspect Model A classification confidence, Model B temporal state, Model C baseline FRP distribution, SVG thermal timeline, and corroborating external registries (Global Energy Monitor, World Bank GFMR).

### 3. Historical Replay Scrubber
* Toggle into **REPLAY Mode** from the top header.
* Slide the chronological timeline across 2025–2026. The backend reconstructs the exact state of every site as of that date with **strictly zero future data leakage**.

### 4. Live Streaming Alert Rail
* Real-time alerts stream via Server-Sent Events (`/api/v1/stream/alerts`).
* Click **LOCATE** on any alert to fly the camera directly to the facility. Analysts can triage and acknowledge alerts directly from the UI.

---

## 📜 Non-Negotiable Core Scientific Rules

1. **750m Physical Resolver**: Never widen the cluster radius to 1,000m. 1,000m introduces spatial chaining and merges distinct industrial plants into artificial mega-clusters.
2. **Never Force `UNKNOWN` to `NONINDUSTRIAL`**: If evidence is inconclusive, preserving `UNKNOWN` is an operational requirement, not a defect.
3. **`INSUFFICIENT_HISTORY` is Not `NORMAL`**: If a site has $<5$ prior active days, Model C will not claim it is operating normally.
4. **Model B is a Deterministic State Engine**: It is not a black-box ML model; it evaluates physical temporal physics.
5. **No Live FIRMS or Earthdata Calls from the Browser**: All API credentials, rate limits, and caching remain strictly server-side.

---

## 📁 Repository Structure

```
sih26162-thermal-ai/
├── DESIGN.md                     # OSIRIS-style Dark Lacquer UI Specification
├── README.md                     # This comprehensive documentation
├── manifest.json                 # Model and data artifact SHA-256 manifest
├── backend/
│   ├── app/
│   │   ├── api/v1/               # FastAPI REST and SSE stream endpoints
│   │   ├── db/                   # SQLAlchemy PostGIS ORM models and session
│   │   ├── engines/              # Frozen Model A, B, C, Resolver & Decision Engines
│   │   ├── schemas/              # Pydantic validation contracts
│   │   └── services/             # NASA FIRMS client, ingestion, and backfill
│   ├── config/                   # Frozen thresholds, features, and decision matrices
│   ├── models/                   # Joblib pipelines, Prithvi-EO weights, and configs
│   ├── scripts/                  # High-speed database bootstrap loader
│   └── tests/                    # 61 comprehensive unit and regression tests
├── frontend/
│   ├── src/
│   │   ├── components/           # Globe MapContainer, Header, Drawer, Rail, Filters
│   │   ├── services/             # API client and Satellite Orbit propagator
│   │   └── types/                # Synchronized TypeScript API contracts
│   └── package.json
└── docs/                         # Authoritative validated research specifications
```

---

## 🏆 Project Team & Credits
Developed for **Smart India Hackathon (SIH26162)**: *AI-Based Detection and Classification of Industrial Fires and Persistent Thermal Sources*.
