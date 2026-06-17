# Platform Upgrade, Rollback, and Migration Plan

This document governs the release lifecycle, minor/major version upgrades, database migration rules, and rollback procedures for the CogniMesh platform.

## 1. Upgrade Compatibility Matrix

CogniMesh adheres to Semantic Versioning (SemVer):

| Version Jump | Schema Migrations | Downtime Requirement | Rollback Capability |
|---|---|---|---|
| **Patch (x.y.z -> x.y.z+1)** | No schema changes | **0 downtime** (rolling update) | Standard downgrade |
| **Minor (x.y.z -> x.y+1.0)** | Backwards-compatible additions | **0 downtime** or brief pause | Supported via backward migration files |
| **Major (x.y.z -> x+1.0.0)** | Potential breaking changes | Planned maintenance window | Requires database restore from pre-upgrade backup |

---

## 2. Platform Upgrade Workflow

1. **Pre-upgrade Backup**: Run backup script to capture current database and catalog states:
   ```bash
   python scripts/db_backup_restore.py backup --db-type sqlite --source state.db --file pre_upgrade.backup
   ```
2. **Apply Migrations**: Execute database migration scripts using Alembic:
   ```bash
   alembic upgrade head
   ```
3. **Deploy Services**: Deploy the new container images using Helm or Docker Compose:
   ```bash
   helm upgrade cognimesh infra/helm/cognimesh -f values.yaml
   ```
4. **Sanity Check**: Run validation gates:
   ```bash
   python scripts/validate_module19.py
   ```

---

## 3. Rollback Procedures

If validation gates fail post-upgrade:

1. **Revert Services**: Downgrade container deployments to pre-upgrade versions:
   ```bash
   helm rollback cognimesh 1
   ```
2. **Revert Schema**: If database migrations were executed, run rollback downgrade commands:
   ```bash
   alembic downgrade -1
   ```
   Or, if schema changes were destructive, restore pre-upgrade snapshot:
   ```bash
   python scripts/db_backup_restore.py restore --db-type sqlite --source state.db --file pre_upgrade.backup
   ```
