---
title: 09 Frontend
source_document: SIH26162 Complete Technical & Implementation Documentation v1.1 (Validated)
source_sections: ["19. OSIRIS-Style Web Command Center"]
status: authoritative
---

# 19. OSIRIS-Style Web Command Center

## 19.1 Frontend stack

Recommended: Next.js + React + TypeScript + MapLibre GL JS + deck.gl. Use server APIs for all data. Recharts/ECharts can be used for site timelines. State/query management can use TanStack Query and a small client store such as Zustand.

## 19.2 Primary screen

| **Region**                    | **Function**                                                                                                                        |
|-------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Center map                    | WebGL map with source sites, raw FIRMS, alert pulses, facility context, imagery overlays and optional 3D terrain/buildings.         |
| Left layer/filter panel       | Toggle FIRMS, industrial/unknown/nonindustrial, B states, C severity, facilities, OSM, WorldCover, HLS; filter time and confidence. |
| Right site-intelligence panel | Selected site A/B/C outputs, provenance, current FRP/detections, alert reason and evidence.                                         |
| Bottom/secondary timeline     | FRP/detection history, B state transitions, C score and alert markers.                                                              |
| Top status bar                | LIVE / REPLAY mode, last FIRMS update, active model version, system health and counts.                                              |
| Alert rail/feed               | Latest HIGH/CRITICAL and review alerts with jump-to-site action.                                                                    |

## 19.3 Site detail tabs

- OVERVIEW - current A/B/C, alert, key statistics, confidence and provenance.

- TIMELINE - max/mean FRP, detections/day, Model C score and Model B state transitions.

- SATELLITE - HLS scene, cloud status, Prithvi probability if used.

- EVIDENCE - nearby/overlapping facility references, coordinate quality, OSM features, WorldCover context.

- RAW FIRMS - individual detections with sensor, date/time, FRP, confidence and version.

- MODEL EXPLANATION - A feature summary, B rule reason and C top anomaly drivers.

## 19.4 Visual behavior

CRITICAL / HIGH alerts may use animated rings or glow, but animation should represent operational priority rather than imply an actual confirmed fire. Unknown sources should have a visually distinct review symbol. Map legends must separate source identity (A), temporal state (B), anomaly (C) and alert severity.
