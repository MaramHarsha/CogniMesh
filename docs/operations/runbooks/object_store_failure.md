# Runbook: Object Store Failure

## Symptoms
- Ingestion jobs fail with `S3ConnectionError` or `BucketNotFound`.
- Lakehouse control fails to register datasets or commit Iceberg snapshots.

## Triage
1. **Verify MinIO/S3 status**:
   Query the MinIO container health status:
   ```bash
   docker compose ps minio
   ```
2. **Inspect MinIO logs**:
   ```bash
   docker compose logs minio --tail=100
   ```
3. **Verify credentials**:
   Ensure `COGNIMESH_S3_ACCESS_KEY` and `COGNIMESH_S3_SECRET_KEY` env variables match in the client services and MinIO.

## Remediation
1. **Restart MinIO**:
   ```bash
   docker compose restart minio
   ```
2. **Recreate storage buckets**:
   If the default `cognimesh-lakehouse` bucket is missing, run startup scripts to recreate it:
   ```bash
   mc alias set local http://localhost:9000 cognimesh cognimesh-secret
   mc mb local/cognimesh-lakehouse
   ```
