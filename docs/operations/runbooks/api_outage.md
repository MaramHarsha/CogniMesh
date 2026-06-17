# Runbook: API Outage

## Symptoms
- Alert `HighApiLatency` or `ElevatedHttpErrors` triggered.
- `GET /health` or `GET /ready` requests fail or timeout on gateway or specific control planes.
- Users report connection errors or HTTP 502/503/504 Bad Gateway.

## Triage
1. **Identify the affected service**:
   Run status command to see which container is down:
   ```bash
   docker compose ps
   ```
   Or for Kubernetes:
   ```bash
   kubectl get pods -n cognimesh
   ```
2. **Inspect logs**:
   For compose:
   ```bash
   docker compose logs <service-name> --tail=100
   ```
   For Kubernetes:
   ```bash
   kubectl logs deployment/<service-name> -n cognimesh --tail=100
   ```
3. **Verify resource consumption**:
   Ensure the host or pod is not out of memory (OOMKilled) or CPU throttled.

## Remediation
1. **Restart the service**:
   If the container stopped or is unresponsive:
   ```bash
   docker compose restart <service-name>
   ```
2. **Scale replicas**:
   If under heavy load, increase replica count in values.yaml or run:
   ```bash
   kubectl scale deployment/<service-name> --replicas=3 -n cognimesh
   ```
3. **Check database connectivity**:
   If the service is failing at startup, ensure the Postgres container is healthy and accepting connections.
