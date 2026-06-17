# Runbook: Failed Ingestion

## Symptoms
- Alert `IngestionFreshness` triggered.
- `ingestion-control` registers a run with status `FAILED` or `STUCK`.
- Downstream tables are not updated.

## Triage
1. **List failed ingestion runs**:
   ```bash
   cognimesh app list --workspace default  # or check ingestion CLI / logs
   ```
2. **Inspect logs**:
   ```bash
   docker compose logs ingestion-control --tail=100
   ```
3. **Verify source accessibility**:
   Ensure connection to the source database, external API, or file path is active.

## Remediation
1. **Trigger run retry**:
   Post a run command or use the ingestion CLI to trigger a re-run:
   ```bash
   curl -X POST http://localhost:8020/v1/ingestion/runs/retry
   ```
2. **Resolve schema drift**:
   If the run failed due to schema changes in the source system, update the source connector schema mapping via `ingestion-control` dashboard or API.
3. **Purge corrupted local Parquet caches**:
   Clear `/var/lib/cognimesh/ingestion-control/raw` if parquet conversions failed due to file corruption.
