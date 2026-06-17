# Backup and Disaster Recovery Guidance

This document defines the backup strategies, disaster recovery runbooks, and target service metrics for the CogniMesh platform.

## 1. RPO & RTO Targets

- **Recovery Point Objective (RPO)**: The maximum acceptable age of data in backup storage in the event of a disaster.
  - **Control-plane Metadata**: **1 hour** (requires hourly Postgres dumps).
  - **Lakehouse Data**: **4 hours** (requires periodic S3 replication or version checkpoints).
- **Recovery Time Objective (RTO)**: The maximum acceptable duration of service downtime before restoration.
  - **Critical query path**: **2 hours** (requires hot standby or automated Helm redeployment).
  - **Analytics pipeline compute**: **8 hours**.

---

## 2. Component Backup Strategies

### A. Postgres Metadata Database
- **Tool**: `pg_dump`
- **Schedule**: Hourly via Kubernetes CronJob or local system crontab.
- **Command**:
  ```bash
  pg_dump -h postgres -U cognimesh -d cognimesh_registry -F c -b -f /backups/postgres_$(date +%F_%T).dump
  ```

### B. Object Store (MinIO/S3)
- **Strategy**: Bucket Versioning + Cross-Region Replication.
- **MinIO Configuration**:
  Enable bucket versioning:
  ```bash
  mc version enable local/cognimesh-lakehouse
  ```
  Mirror raw parquet datasets to secondary backup bucket:
  ```bash
  mc mirror --watch local/cognimesh-lakehouse backup-s3/cognimesh-lakehouse-backup
  ```

### C. Nessie Catalog
- **Strategy**: Nessie transaction logs are stored in the backing metadata database. Since Nessie relies on the metadata store (or Key-Value store), backing up the underlying database (e.g. Postgres or DynamoDB) preserves the entire catalog history, including branches, tags, and commits.

### D. Keycloak Realm
- **Strategy**: Export Keycloak configurations at build time or via Admin CLI:
  ```bash
  /opt/keycloak/bin/kc.sh export --dir /backups/keycloak-export --realm cognimesh
  ```
