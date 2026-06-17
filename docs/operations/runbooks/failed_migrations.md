# Runbook: Failed Migrations

## Symptoms
- A service fails to boot with errors like `sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedColumn) column "..." does not exist`.
- Alembic/migration command fails during service upgrade.

## Triage
1. **Check Alembic history status**:
   ```bash
   docker compose run --rm object-registry alembic current
   ```
2. **Review migration logs**:
   Identify which migration file (e.g. `0003_lineage_provenance_ledger.py`) failed and the exact SQL error encountered.

## Remediation
1. **Rollback to last known good revision**:
   ```bash
   docker compose run --rm object-registry alembic downgrade -1
   ```
2. **Resolve locks / partial schema state**:
   If a migration failed midway (e.g. DDL executed partially on engines without transactional DDL), connect directly to the database and manually drop/alter table states, then mark migration as completed using `alembic stamp`.
3. **Restore from backup**:
   If the metadata became corrupted, run the restore script `python scripts/db_backup_restore.py restore --file <backup_path>` to recover the last consistent schema.
