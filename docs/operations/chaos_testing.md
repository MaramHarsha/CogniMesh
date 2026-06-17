# Chaos Testing Plan

This document outlines the chaos engineering experiments designed to verify the resilience of the CogniMesh platform under abnormal infrastructure conditions.

## 1. Chaos Scenarios & Expected Outcomes

| Scenario | Injector Command | Expected Outcome | Recovery Verification |
|---|---|---|---|
| **Service Outage** | `docker compose stop query-service` | Gateway routes traffic elsewhere or returns 503. Downstream apps continue reading from cache. | Start service and ensure metrics scrape resumes. |
| **Network Latency** | `tc qdisc add dev eth0 root netem delay 200ms` | Average request latency alert triggers. Request handlers do not crash. | Remove tc rule, ensure latency drops to baseline (<10ms). |
| **Postgres Crash** | `docker compose kill postgres` | Health endpoints of dependant services report failure status. Lineage ledger queues writes locally. | Restart postgres, verify schema consistency and replay of lineage. |
| **MinIO/S3 Outage** | `docker compose stop minio` | Object ingestion fails gracefully. No metadata is lost. | Restart minio, retry failed ingestion runs. |

---

## 2. Execution Process

1. **Establish Baseline**: Verify OQS latency is `< 20ms` and system metrics are nominal.
2. **Inject Chaos**: Run the injector command in a dev/staging environment.
3. **Verify Observability**: Ensure the corresponding Prometheus Alert (e.g. `HighApiLatency` or `ElevatedHttpErrors`) triggers within 1-2 minutes.
4. **Halt Chaos & Recover**: Restore the infrastructure component.
5. **Post-Mortem**: Verify data consistency and trace/span propagation across recovered services.
