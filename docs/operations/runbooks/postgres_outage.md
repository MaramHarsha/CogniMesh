# Runbook: Postgres Outage

## Symptoms
- Services report database connection timeouts or `OperationalError: connection to server at "postgres" failed`.
- Alert `ElevatedHttpErrors` triggered with database error traces.

## Triage
1. **Check Postgres container status**:
   ```bash
   docker compose ps postgres
   ```
2. **Inspect database logs**:
   ```bash
   docker compose logs postgres --tail=100
   ```
3. **Check connection pools**:
   Check if the database has reached `max_connections` (usually 100 on default postgres images).

## Remediation
1. **Restart Postgres**:
   If unresponsive:
   ```bash
   docker compose restart postgres
   ```
2. **Increase connection limit**:
   If max connections is reached, terminate idle connections or update Postgres `max_connections` config in custom configuration file and restart.
3. **Verify disk space**:
   If Postgres stopped, check if the host filesystem is 100% full. Free up space or expand persistent volume claims.
