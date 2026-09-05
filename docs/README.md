# SIH26162 implementation documentation index

These files are optimized for coding agents. They are split from the validated v1.1 technical documentation without changing frozen model logic.

## Mandatory read order

1. `00_overview.md` - current status, problem, frozen principles.
2. `01_data_and_ground_truth.md` - 750 m resolver and ground-truth rules.
3. `02_model_a.md` - production Model A and exact A-Core feature set.
4. `03_model_b.md` - deterministic temporal-state engine.
5. `04_model_c.md` - frozen V3 anomaly engine.
6. `05_validation_claims.md` - what may and may not be claimed.
7. `06_decision_engine.md` - proposed, **not yet frozen**, A+B+C alert policy.
8. `07_firms_integration.md` - 2026 backfill, live FIRMS, HLS/Prithvi, external evidence.
9. `08_backend_and_db.md` - runtime packaging, repository, PostGIS and FastAPI contracts.
10. `09_frontend.md` - OSIRIS-style command center requirements.
11. `10_deployment_ops.md` - live cycle, replay, deployment, security/licensing.
12. `11_testing_roadmap.md` - regression gates and exact implementation phases.
13. `12_risks.md` - limitations and future work.
14. `13_artifacts_env_contract.md` - artifact inventory, environment variables, unified JSON example.
15. `14_references.md` - external references.

`99_full_validated_source.md` is a fidelity conversion of the validated source document and is the tie-breaker if a split file seems ambiguous.

Machine-readable frozen values are under `../backend/config/`.
