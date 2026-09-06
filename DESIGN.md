# SIH26162 OSIRIS Command Center — Design System Specification

## 1. Design Philosophy & Register

- **Operational Register (`Operate` Mode):** This interface is a high-density, mission-critical decision support cockpit for analysts, environmental regulators, and disaster response teams. Function, scanability, spatial clarity, and data density take absolute precedence over decorative consumer aesthetics.
- **Visual Stance:** Nocturnal command center grounded in deep dark lacquer (`#090d16` / `#0f172a`), accented by precise telemetry hairlines, crisp micro-typography, and high-contrast semantic indicators.
- **Information Architecture:**
  - **Top Navigation & Telemetry:** Mode switcher (LIVE / REPLAY), live WebSocket/SSE heartbeat status, active model stack badge (`2026-09-04-r1`), and global national summary statistics.
  - **Left Rail (Layer & Filter Matrix):** Multi-dimensional filter toggles for Model A (identity), Model B (temporal state), Model C (anomaly severity), Decision Engine alerts, and GIS evidence overlays.
  - **Center Viewport (Geospatial Cockpit):** WebGL MapLibre map with GPU point clusters, high-severity alert halos, and raw FIRMS hotspot vectors.
  - **Right Drawer (Analyst Site Intelligence):** Multi-tab deep inspection panel (Overview, Thermal Timeline, Satellite HLS/Prithvi, Corroborating Evidence, and Raw Detections).
  - **Bottom Scrubber (Historical Replay Control):** Chronological playback timeline for backtesting and historical scenario evaluation.

---

## 2. Color Palette & Semantic Tokens

### 2.1 Surfaces & Chrome (Dark Lacquer System)
```css
--surface-ground: #070a12;       /* Deepest canvas background */
--surface-panel: #0b1120;        /* Sidebar and panel background */
--surface-card: #111a2e;         /* Elevated cards and drawer sections */
--surface-hover: #18243e;        /* Interactive hover states */
--surface-active: #1f2f52;       /* Selected / active tab states */

--border-subtle: rgba(255, 255, 255, 0.08); /* 1px hairline panel separators */
--border-contrast: rgba(255, 255, 255, 0.16);/* Focus / active border */
--border-glow: rgba(56, 189, 248, 0.25);    /* Telemetry glow */

--text-primary: #f8fafc;        /* High-emphasis headers and values */
--text-secondary: #94a3b8;      /* Body labels, table cells */
--text-muted: #64748b;          /* Metadata, timestamps, units */
--text-disabled: #475569;       /* Disabled controls */
```

### 2.2 Semantic Model Separation (Non-Negotiable)

The interface strictly preserves independent visual languages for all 4 core intelligence systems:

#### A. Model A: Source Identity (Fill & Marker Shape)
- **INDUSTRIAL:** `#f59e0b` (Amber Gold) — Hexagon / Industrial Tower icon.
- **NONINDUSTRIAL:** `#10b981` (Emerald Green) — Leaf / Terrain icon.
- **UNKNOWN:** `#818cf8` (Indigo / Violet) — Distinct Question / Radar icon.
  *(Rule: Never visually group or alias UNKNOWN as NONINDUSTRIAL).*

#### B. Model B: Temporal Operating State (Border & Badge Tone)
- **PERSISTENT:** `#06b6d4` (Solid Cyan) — Continuous pulse indicator.
- **REACTIVATED:** `#a855f7` (Electric Purple) — Lightning / return indicator.
- **INTERMITTENT:** `#38bdf8` (Sky Blue) — Broken ring indicator.
- **NEW:** `#14b8a6` (Teal) — Sparkle / new source tag.
- **DORMANT:** `#64748b` (Muted Slate) — Low-opacity dim ring.

#### C. Model C: Unsupervised Thermal Anomaly (Intensity & Chart Fill)
- **CRITICAL:** `#ef4444` (Vivid Crimson, $\ge 0.99$ percentile).
- **ANOMALOUS:** `#f97316` (Deep Orange, $\ge 0.95$ percentile).
- **ELEVATED:** `#eab308` (Warm Yellow, $\ge 0.90$ percentile).
- **NORMAL:** `#22c55e` (Calm Green, $< 0.90$ percentile).
- **INSUFFICIENT_HISTORY:** `#6b7280` (Dashed Slate — *Rule: Never display as NORMAL*).
- **NO_RECENT_EVENT:** `#4b5563` (Dim Slate — *Used when site has no current event*).

#### D. Decision Engine: Operational Alerts (Banner & Halos)
- **CRITICAL:** `#ef4444` (Glowing Red halo + alert rail priority).
- **HIGH:** `#f97316` (Orange halo).
- **MEDIUM:** `#eab308` (Yellow badge).
- **LOW:** `#06b6d4` (Cyan badge).
- **INFO / NO_ALERT:** `#64748b` (Subdued gray).

#### E. Corroborating Facility Evidence
- **GEM Thermal Power Plants:** `#3b82f6` (Cobalt Blue).
- **World Bank Gas Flaring:** `#f59e0b` (Flaring Flame Gold).
- **ICAR Crop Residue Burning:** `#ea580c` (Fire Orange).
- **FSI Forest Wildfire Perimeters:** `#dc2626` (Crimson Perimeter).

---

## 3. Typography Hierarchy

- **Font Family:** Inter, system-ui, -apple-system, sans-serif.
- **Monospace Family:** JetBrains Mono, Fira Code, ui-monospace (for coordinates, FRP, timestamps, fingerprints, and site IDs).
- **Type Scale:**
  - `Display / Header 1`: 1.25rem (20px) / font-bold / tracking-tight
  - `Section Header 2`: 1.0rem (16px) / font-semibold
  - `Card / Drawer Subhead`: 0.875rem (14px) / font-medium / text-primary
  - `Body / Telemetry Label`: 0.8125rem (13px) / font-normal / text-secondary
  - `Metadata / Unit / Badge`: 0.6875rem (11px) / font-semibold / uppercase / tracking-wider

---

## 4. Component Standards

### 4.1 Status Badges & Pills
- Compact padding (`py-0.5 px-2`), `rounded-full` or `rounded-sm`.
- Semi-transparent background (15% opacity) with 1px matching border and 100% foreground text for maximum readability against dark lacquer.

### 4.2 Map Layering & WebGL Rendering
- Base Layer: Dark carto / CartoDB Dark Matter or MapLibre Positron Dark vector tiles.
- Site Markers: Circular / hexagonal GPU symbols sized proportionally to zoom level.
- Interactive Popover: Instant 1-line tooltip showing Site ID, Class, State, and Current Status on hover; click opens the right intelligence drawer.

### 4.3 Analyst Intelligence Drawer
- Width: Fixed 420px–480px responsive side sheet docked to the right edge.
- Tab bar with active underline indicator in primary cyan/gold.
- Scrollable content area with zero layout shifts during data hydration.

### 4.4 Real-Time Telemetry Feed
- Floating / collapsible alert rail with live pulsing indicator on new SSE messages.
- Jump-to-site click behavior centering the viewport and selecting the targeted site.
