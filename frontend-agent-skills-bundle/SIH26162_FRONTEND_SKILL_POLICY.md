# SIH26162 Frontend Skill Policy

## Authority order

When instructions conflict, follow this order:

1. SIH26162 technical/product requirements and data semantics
2. Existing application behavior and API contracts
3. Project `DESIGN.md`
4. Explicit task instruction
5. Impeccable for product/dashboard UI
6. Taste for compatible surfaces
7. Img2ThreeJS only for explicit 3D work

A design skill must never change Model A/B/C semantics, thresholds, alert meanings, evidence interpretation, or provenance.

## Design MD / Awesome DESIGN.md

Use it to establish or intentionally revise the project's visual system. Pick references for mood, hierarchy, typography, tokens, and component language, then produce a project-specific `DESIGN.md`.

Do not continuously switch brand references during normal feature work. Once the SIH26162 `DESIGN.md` is approved, it is the visual source of truth.

## Impeccable

Use Impeccable as the primary design/review skill for the SIH26162 command center because it explicitly supports dashboards and product UI.

Recommended workflow:

1. Read product requirements and `DESIGN.md`.
2. Shape/build the UI.
3. Run an Impeccable critique/audit/polish pass after the feature works.
4. Fix justified issues in one bounded pass.
5. Verify desktop and responsive states.

Prioritize scanability, hierarchy, accessibility, responsiveness, loading/error states, data density, and consistency.

## Taste Skill

The upstream default Taste skill currently targets landing pages, portfolios, and redesigns and explicitly says it is not for dashboards, data tables, or multi-step product UI.

Therefore for SIH26162:

- Use Taste for a public landing page, demo intro, presentation microsite, or other marketing-style surface.
- Do not automatically apply Taste to the operational map dashboard.
- If you intentionally borrow one of its anti-slop rules for the dashboard, it must remain subordinate to `DESIGN.md` and Impeccable's product/Operate guidance.

## Img2ThreeJS

Use only when the user explicitly asks for a procedural Three.js reconstruction or a custom 3D scene/object based on a reference image.

Do not use it for:

- the main geospatial map
- FIRMS markers
- OSM/facility layers
- WorldCover layers
- charts
- ordinary dashboard decoration

MapLibre + deck.gl remain the primary geospatial visualization stack.

## SIH26162 semantic UI rules

The frontend must keep these concepts visually distinct:

- Model A: source identity
- Model B: temporal state
- Model C: anomaly state
- Decision engine: operational alert
- Evidence: corroboration/context

Never imply:

- `UNKNOWN` = `NONINDUSTRIAL`
- `INSUFFICIENT_HISTORY` = `NORMAL`
- `CRITICAL` = confirmed industrial fire
- missing OSM/GEM evidence = negative evidence
- Prithvi can veto a confident A-Core result

## Suggested prompt header

Use this at the start of major frontend tasks:

> Read the SIH26162 requirements, `DESIGN.md`, and `SIH26162_FRONTEND_SKILL_POLICY.md` first. Treat the dashboard as operational product UI. Use Impeccable as the primary frontend design/review skill. Use Taste only where its scope is compatible. Do not invoke Img2ThreeJS unless the task explicitly requires 3D. Preserve all A/B/C and evidence semantics.
