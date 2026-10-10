# Acceptance Criteria

Criteria below are release gates, not claims that they currently pass.

| Area | Measurable gate |
|---|---|
| Correctness | State-machine transition/property suite covers every allowed/forbidden edge and budget invariant; zero unexplained failures in required CI. |
| Contracts | Python/TypeScript contract fixtures pass across supported versions; incompatible major schema is rejected; public API consumer example builds. |
| Security | Threat model reviewed; secret-canary scans clean; tenant negative tests pass for every persistence API; SSRF/policy bypass/security suites have no unresolved critical/high findings or documented accepted exception. |
| Reliability | Crash injection at provider/tool/persistence/checkpoint boundaries records confirmed or ambiguous outcome correctly; recovery never duplicates an unqualified irreversible operation. |
| Database | Empty and upgrade migrations pass; rollback/forward-fix plan documented; transaction/CAS tests; restore drill records measured outcome. |
| Provider compatibility | Each claimed adapter passes shared fixtures for declared capabilities and errors; unsupported capability is rejected before request. |
| Performance | Workload, hardware, concurrency, model and error distributions published; service latency/throughput objectives selected from evidence, not invented in this blueprint. |
| Observability | Correlation IDs across spans/events; redaction tests; exporter outage behavior measured; metrics cardinality bounded. |
| API stability | Compatibility matrix, deprecation and checkpoint migration tests; changelog entry per public change. |
| Build/release | Reproducible package/container build, clean install test, dependency/SBOM/provenance checks as supported, artifacts tied to source revision. |
| Operations | Backup/restore, incident procedures, secrets rotation, resource limits, deployment upgrade and rollback/forward recovery tested. |
| Documentation | Every feature has all required sections and unique IDs; links and diagrams validated; no unsupported claims. |

Production support requires evidence artifacts, named supported configuration, residual risk acceptance, and maintainer sign-off. Passing isolated tests is not a certification.
