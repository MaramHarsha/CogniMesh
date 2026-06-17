# Service Level Objectives (SLOs) & Error Budgets

This document outlines the Service Level Indicators (SLIs), Service Level Objectives (SLOs), and error budget guidelines for the CogniMesh platform.

## 1. Service Level Indicators (SLIs)

We measure three core indicators:

1. **Availability**: The percentage of successful HTTP requests (status codes `< 500`).
2. **Latency**: The duration of API request processing.
3. **Data Freshness**: The time delay between source data change and Object Query index update.

---

## 2. Service Level Objectives (SLOs)

Our targets are defined over a rolling **30-day window**:

| Indicator | Target | Measurement |
|---|---|---|
| **API Availability** | **99.9%** | Count of HTTP non-5xx / Total HTTP requests |
| **API Latency (p95)** | **< 200ms** | Processing time of 95% of queries |
| **API Latency (p99)** | **< 500ms** | Processing time of 99% of queries |
| **Ingestion Freshness** | **< 15 minutes** | Delay between physical data snapshot and Object registry update |
| **Policy Decision Latency** | **< 50ms** | Time for Policy Engine check evaluation |

---

## 3. Error Budget Guidance

The error budget is the allowed rate of failure over the 30-day window.

- **99.9% Availability SLO** allows a **0.1% error budget**.
- For 10,000,000 requests, the error budget allows **10,000 failed requests**.

### Budget Depletion Response Guidelines

- **> 80% Error Budget Remaining**: Normal operations. Feature development prioritized.
- **50% - 80% Error Budget Remaining**: Alert triggered. On-call engineer investigates error vectors.
- **20% - 50% Error Budget Remaining**: Weekly review required. Mitigate recurring root causes.
- **< 20% Error Budget Remaining**: Strict freeze on new feature releases. Engineers pivot to reliability, scaling, and observability fixes.
