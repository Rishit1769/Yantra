# Monitoring

Proposed OpenTelemetry traces and metrics plus structlog JSON logs. Monitor request/run counts, latency, queue depth, provider/tool error categories, state age, approval age, persistence availability, database pool saturation, token/cost when known, recovery outcomes, worker resource use, and retention jobs. Use bounded-cardinality labels; identifiers belong in traces/logs, not metric labels.

Redact content before export, set sampling/retention, protect audit access, alert on security-relevant policy violations and recovery backlog, and test exporter outage. Prometheus/Grafana are optional integrations. No metrics or SLOs are currently measured.
