from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.security import RequestContext
from app.dbt.artifact_parser import contract_from_test, parse_manifest, run_statuses
from app.models.semantic import (
    ArtifactImportRequest,
    CatalogSyncRequest,
    DbtProjectCreate,
    InterfaceCreate,
    ObjectMappingCreate,
    PromotionRequest,
)


JSON_FIELDS = {
    "columns",
    "config",
    "entities",
    "interfaces",
    "lineage_event",
    "lineage_events",
    "links",
    "properties",
    "registry_payload",
    "tags",
    "validation",
}

VALUE_TYPES: dict[str, dict[str, Any]] = {
    "string": {
        "backing": "string",
        "description": "Free-form text property",
        "sql_types": {"VARCHAR", "TEXT", "CHAR", "STRING", "NVARCHAR"},
    },
    "integer": {
        "backing": "integer",
        "description": "Whole-number property",
        "sql_types": {"INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT"},
    },
    "decimal": {
        "backing": "decimal",
        "description": "Fractional numeric property",
        "sql_types": {"DECIMAL", "NUMERIC", "DOUBLE", "FLOAT", "REAL"},
    },
    "boolean": {
        "backing": "boolean",
        "description": "True/false property",
        "sql_types": {"BOOLEAN", "BOOL"},
    },
    "date": {
        "backing": "date",
        "description": "Calendar date property",
        "sql_types": {"DATE"},
    },
    "timestamp": {
        "backing": "timestamp",
        "description": "Point-in-time property",
        "sql_types": {"TIMESTAMP", "TIMESTAMP WITH TIME ZONE", "TIMESTAMPTZ", "DATETIME"},
    },
    "email": {
        "backing": "string",
        "description": "Shared semantic type for email addresses",
        "sql_types": {"VARCHAR", "TEXT", "CHAR", "STRING", "NVARCHAR"},
    },
    "identifier": {
        "backing": "string_or_integer",
        "description": "Shared semantic type for stable entity identifiers",
        "sql_types": {"VARCHAR", "TEXT", "CHAR", "STRING", "NVARCHAR", "INTEGER", "INT", "BIGINT", "SMALLINT", "UUID"},
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def from_json(value: str | None, default: Any) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)


def normalize_sql_type(data_type: str | None) -> str | None:
    if not data_type:
        return None
    return data_type.split("(")[0].strip().upper()


class SemanticRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Path(settings.state_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(settings.state_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS dbt_projects (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              workspace_id TEXT NOT NULL,
              namespace TEXT NOT NULL,
              adapter_type TEXT NOT NULL,
              dbt_version TEXT,
              description TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS artifact_imports (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              dbt_version TEXT,
              adapter_type TEXT,
              sources_imported INTEGER NOT NULL,
              models_imported INTEGER NOT NULL,
              tests_imported INTEGER NOT NULL,
              columns_documented INTEGER NOT NULL,
              run_results_applied INTEGER NOT NULL,
              lineage_events TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS datasets (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              unique_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              database TEXT,
              schema_name TEXT,
              name TEXT NOT NULL,
              identifier TEXT NOT NULL,
              description TEXT,
              columns TEXT NOT NULL,
              materialization TEXT NOT NULL,
              tags TEXT NOT NULL,
              last_run_status TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (project_id, unique_id)
            );

            CREATE TABLE IF NOT EXISTS contracts (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              test_unique_id TEXT NOT NULL,
              dataset_unique_id TEXT,
              contract_type TEXT NOT NULL,
              column_name TEXT,
              config TEXT NOT NULL,
              severity TEXT NOT NULL,
              status TEXT NOT NULL,
              description TEXT,
              last_run_at TEXT,
              UNIQUE (project_id, test_unique_id)
            );

            CREATE TABLE IF NOT EXISTS interfaces (
              id TEXT PRIMARY KEY,
              api_name TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL,
              description TEXT,
              properties TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS object_mappings (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              model_unique_id TEXT NOT NULL,
              object_api_name TEXT NOT NULL,
              display_name TEXT NOT NULL,
              description TEXT,
              primary_key_property TEXT NOT NULL,
              properties TEXT NOT NULL,
              links TEXT NOT NULL,
              interfaces TEXT NOT NULL,
              status TEXT NOT NULL,
              validation TEXT,
              registry_payload TEXT,
              lineage_event TEXT,
              promoted_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS catalog_syncs (
              id TEXT PRIMARY KEY,
              target TEXT NOT NULL,
              status TEXT NOT NULL,
              entities TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor

    def _fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        row = self.connection.execute(sql, params).fetchone()
        return self._row(row) if row else None

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [self._row(row) for row in self.connection.execute(sql, params).fetchall()]

    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for field in JSON_FIELDS.intersection(item):
            default: Any = [] if field in {"columns", "interfaces", "lineage_events", "links", "properties", "tags"} else {}
            item[field] = from_json(item[field], default)
        if "run_results_applied" in item:
            item["run_results_applied"] = bool(item["run_results_applied"])
        return item

    # ------------------------------------------------------------------ projects

    def create_project(self, payload: DbtProjectCreate) -> dict[str, Any]:
        existing = self._fetch_one("SELECT * FROM dbt_projects WHERE name = ?", (payload.name,))
        if existing:
            raise ValueError(f"dbt project {payload.name} already exists")
        project_id = new_id("dbtp")
        now = utc_now()
        self._execute(
            """
            INSERT INTO dbt_projects (id, name, workspace_id, namespace, adapter_type, dbt_version, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                payload.name,
                payload.workspace_id,
                payload.namespace,
                payload.adapter_type,
                payload.dbt_version,
                payload.description,
                now,
                now,
            ),
        )
        return self.get_project(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM dbt_projects ORDER BY created_at")

    def get_project(self, project_id: str) -> dict[str, Any]:
        project = self._fetch_one("SELECT * FROM dbt_projects WHERE id = ?", (project_id,))
        if project is None:
            raise ValueError(f"dbt project {project_id} was not found")
        return project

    # ------------------------------------------------------------------ artifact import

    def import_artifacts(self, project_id: str, payload: ArtifactImportRequest, context: RequestContext) -> dict[str, Any]:
        project = self.get_project(project_id)
        parsed = parse_manifest(payload.manifest, payload.catalog)
        statuses = run_statuses(payload.run_results)
        now = utc_now()

        nodes_by_uid: dict[str, dict[str, Any]] = {}
        for node in parsed["sources"] + parsed["models"]:
            nodes_by_uid[node["unique_id"]] = node
            self._upsert_dataset(project_id, node, statuses.get(node["unique_id"]), now)

        for test_node in parsed["tests"]:
            contract = contract_from_test(test_node)
            self._upsert_contract(project_id, contract, statuses.get(contract["test_unique_id"]), now)

        import_id = new_id("dbti")
        lineage_events = [
            self._lineage_event_for_model(import_id, project, parsed, model, nodes_by_uid, statuses, context)
            for model in parsed["models"]
        ]
        columns_documented = sum(
            1
            for node in nodes_by_uid.values()
            for column in node["columns"]
            if column.get("description")
        )
        dbt_version = parsed["metadata"].get("dbt_version") or project["dbt_version"]
        adapter_type = parsed["metadata"].get("adapter_type") or project["adapter_type"]
        self._execute(
            "UPDATE dbt_projects SET dbt_version = ?, adapter_type = ?, updated_at = ? WHERE id = ?",
            (dbt_version, adapter_type, now, project_id),
        )
        self._execute(
            """
            INSERT INTO artifact_imports (
              id, project_id, dbt_version, adapter_type, sources_imported, models_imported,
              tests_imported, columns_documented, run_results_applied, lineage_events, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id,
                project_id,
                dbt_version,
                adapter_type,
                len(parsed["sources"]),
                len(parsed["models"]),
                len(parsed["tests"]),
                columns_documented,
                1 if payload.run_results else 0,
                to_json(lineage_events),
                now,
            ),
        )
        return self._fetch_one("SELECT * FROM artifact_imports WHERE id = ?", (import_id,))

    def list_imports(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self._fetch_all("SELECT * FROM artifact_imports WHERE project_id = ? ORDER BY created_at", (project_id,))

    def project_lineage(self, project_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for record in self.list_imports(project_id):
            events.extend(record["lineage_events"])
        return events

    def _upsert_dataset(self, project_id: str, node: dict[str, Any], status: str | None, now: str) -> None:
        existing = self._fetch_one(
            "SELECT * FROM datasets WHERE project_id = ? AND unique_id = ?",
            (project_id, node["unique_id"]),
        )
        if existing:
            self._execute(
                """
                UPDATE datasets
                SET database = ?, schema_name = ?, name = ?, identifier = ?, description = ?,
                    columns = ?, materialization = ?, tags = ?, last_run_status = COALESCE(?, last_run_status), updated_at = ?
                WHERE id = ?
                """,
                (
                    node["database"],
                    node["schema_name"],
                    node["name"],
                    node["identifier"],
                    node["description"],
                    to_json(node["columns"]),
                    node["materialization"],
                    to_json(node["tags"]),
                    status,
                    now,
                    existing["id"],
                ),
            )
            return
        self._execute(
            """
            INSERT INTO datasets (
              id, project_id, unique_id, kind, database, schema_name, name, identifier,
              description, columns, materialization, tags, last_run_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("dset"),
                project_id,
                node["unique_id"],
                node["kind"],
                node["database"],
                node["schema_name"],
                node["name"],
                node["identifier"],
                node["description"],
                to_json(node["columns"]),
                node["materialization"],
                to_json(node["tags"]),
                status,
                now,
                now,
            ),
        )

    def _upsert_contract(self, project_id: str, contract: dict[str, Any], status: str | None, now: str) -> None:
        existing = self._fetch_one(
            "SELECT * FROM contracts WHERE project_id = ? AND test_unique_id = ?",
            (project_id, contract["test_unique_id"]),
        )
        resolved_status = status or "unknown"
        last_run_at = now if status else None
        if existing:
            self._execute(
                """
                UPDATE contracts
                SET dataset_unique_id = ?, contract_type = ?, column_name = ?, config = ?, severity = ?,
                    status = ?, description = ?, last_run_at = COALESCE(?, last_run_at)
                WHERE id = ?
                """,
                (
                    contract["dataset_unique_id"],
                    contract["contract_type"],
                    contract["column_name"],
                    to_json(contract["config"]),
                    contract["severity"],
                    resolved_status if status else existing["status"],
                    contract["description"],
                    last_run_at,
                    existing["id"],
                ),
            )
            return
        self._execute(
            """
            INSERT INTO contracts (
              id, project_id, test_unique_id, dataset_unique_id, contract_type, column_name,
              config, severity, status, description, last_run_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("dcon"),
                project_id,
                contract["test_unique_id"],
                contract["dataset_unique_id"],
                contract["contract_type"],
                contract["column_name"],
                to_json(contract["config"]),
                contract["severity"],
                resolved_status,
                contract["description"],
                last_run_at,
            ),
        )

    def _lineage_event_for_model(
        self,
        import_id: str,
        project: dict[str, Any],
        parsed: dict[str, Any],
        model: dict[str, Any],
        nodes_by_uid: dict[str, dict[str, Any]],
        statuses: dict[str, str],
        context: RequestContext,
    ) -> dict[str, Any]:
        parents = parsed["parent_map"].get(model["unique_id"]) or model.get("depends_on") or []
        status = statuses.get(model["unique_id"])
        project_name = parsed["metadata"].get("project_name") or project["name"]
        inputs = []
        for parent_uid in parents:
            parent = nodes_by_uid.get(parent_uid)
            if parent is None:
                continue
            inputs.append(
                {
                    "namespace": f"{parent['database']}.{parent['schema_name']}",
                    "name": parent["identifier"],
                    "facets": {"unique_id": parent_uid, "kind": parent["kind"]},
                }
            )
        return {
            "eventType": "FAIL" if status == "failed" else "COMPLETE",
            "eventTime": utc_now(),
            "producer": "https://github.com/cognimesh/cognimesh/services/semantic-control",
            "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
            "run": {
                "runId": import_id,
                "facets": {
                    "cognimesh": {
                        "actor": context.actor,
                        "workspace_id": context.workspace_id or project["workspace_id"],
                        "purpose": context.purpose,
                        "project_id": project["id"],
                        "dbt_version": parsed["metadata"].get("dbt_version"),
                        "adapter_type": parsed["metadata"].get("adapter_type"),
                        "model_unique_id": model["unique_id"],
                    }
                },
            },
            "job": {"namespace": f"cognimesh.dbt.{project_name}", "name": model["name"]},
            "inputs": inputs,
            "outputs": [
                {
                    "namespace": f"{model['database']}.{model['schema_name']}",
                    "name": model["identifier"],
                    "facets": {
                        "unique_id": model["unique_id"],
                        "materialization": model["materialization"],
                        "run_status": status or "not_run",
                    },
                }
            ],
        }

    # ------------------------------------------------------------------ datasets and contracts

    def list_datasets(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            return self._fetch_all("SELECT * FROM datasets WHERE project_id = ? ORDER BY unique_id", (project_id,))
        return self._fetch_all("SELECT * FROM datasets ORDER BY unique_id")

    def get_dataset(self, project_id: str, unique_id: str) -> dict[str, Any]:
        dataset = self._fetch_one(
            "SELECT * FROM datasets WHERE project_id = ? AND unique_id = ?",
            (project_id, unique_id),
        )
        if dataset is None:
            raise ValueError(f"Dataset {unique_id} was not found")
        return dataset

    def list_contracts(self, project_id: str | None = None, dataset_unique_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM contracts"
        clauses, params = [], []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if dataset_unique_id:
            clauses.append("dataset_unique_id = ?")
            params.append(dataset_unique_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._fetch_all(sql + " ORDER BY test_unique_id", tuple(params))

    # ------------------------------------------------------------------ interfaces and value types

    def value_types(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "backing": spec["backing"],
                "description": spec["description"],
                "compatible_sql_types": sorted(spec["sql_types"]),
            }
            for name, spec in VALUE_TYPES.items()
        ]

    def create_interface(self, payload: InterfaceCreate) -> dict[str, Any]:
        if self._fetch_one("SELECT * FROM interfaces WHERE api_name = ?", (payload.api_name,)):
            raise ValueError(f"Interface {payload.api_name} already exists")
        for prop in payload.properties:
            if prop.value_type not in VALUE_TYPES:
                raise ValueError(f"Interface property {prop.api_name} uses unknown value type {prop.value_type}")
        interface_id = new_id("iface")
        self._execute(
            "INSERT INTO interfaces (id, api_name, display_name, description, properties, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                interface_id,
                payload.api_name,
                payload.display_name,
                payload.description,
                to_json([prop.model_dump() for prop in payload.properties]),
                utc_now(),
            ),
        )
        return self._fetch_one("SELECT * FROM interfaces WHERE id = ?", (interface_id,))

    def list_interfaces(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM interfaces ORDER BY api_name")

    # ------------------------------------------------------------------ object mappings

    def create_mapping(self, payload: ObjectMappingCreate, context: RequestContext) -> dict[str, Any]:
        project = self.get_project(payload.project_id)
        dataset = self.get_dataset(project["id"], payload.model_unique_id)
        if dataset["kind"] != "model":
            raise ValueError("Object mappings must target a dbt model, not a source")
        for prop in payload.properties:
            if prop.value_type not in VALUE_TYPES:
                raise ValueError(f"Property {prop.api_name} uses unknown value type {prop.value_type}")

        column_docs = {column["name"]: column.get("description") for column in dataset["columns"]}
        properties = []
        for prop in payload.properties:
            data = prop.model_dump()
            if not data.get("description"):
                data["description"] = column_docs.get(prop.column_name)
            properties.append(data)

        mapping_id = new_id("omap")
        now = utc_now()
        self._execute(
            """
            INSERT INTO object_mappings (
              id, project_id, model_unique_id, object_api_name, display_name, description,
              primary_key_property, properties, links, interfaces, status, validation,
              registry_payload, lineage_event, promoted_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mapping_id,
                payload.project_id,
                payload.model_unique_id,
                payload.object_api_name,
                payload.display_name,
                payload.description or dataset["description"],
                payload.primary_key_property,
                to_json(properties),
                to_json([link.model_dump() for link in payload.links]),
                to_json(payload.interfaces),
                "draft",
                None,
                None,
                None,
                None,
                now,
                now,
            ),
        )
        return self.get_mapping(mapping_id)

    def list_mappings(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            return self._fetch_all("SELECT * FROM object_mappings WHERE project_id = ? ORDER BY created_at", (project_id,))
        return self._fetch_all("SELECT * FROM object_mappings ORDER BY created_at")

    def get_mapping(self, mapping_id: str) -> dict[str, Any]:
        mapping = self._fetch_one("SELECT * FROM object_mappings WHERE id = ?", (mapping_id,))
        if mapping is None:
            raise ValueError(f"Object mapping {mapping_id} was not found")
        return mapping

    def validate_mapping(self, mapping_id: str) -> dict[str, Any]:
        mapping = self.get_mapping(mapping_id)
        dataset = self.get_dataset(mapping["project_id"], mapping["model_unique_id"])
        errors: list[dict[str, str]] = []
        warnings: list[str] = []

        property_names = {prop["api_name"] for prop in mapping["properties"]}
        if mapping["primary_key_property"] not in property_names:
            errors.append(
                {
                    "code": "missing_primary_key",
                    "message": f"Primary key property {mapping['primary_key_property']} is not defined in the mapping properties",
                }
            )

        duplicate = self._fetch_one(
            "SELECT * FROM object_mappings WHERE object_api_name = ? AND id != ?",
            (mapping["object_api_name"], mapping_id),
        )
        if duplicate:
            errors.append(
                {
                    "code": "duplicate_api_name",
                    "message": f"Object API name {mapping['object_api_name']} is already used by mapping {duplicate['id']}",
                }
            )

        columns = {column["name"]: column for column in dataset["columns"]}
        for prop in mapping["properties"]:
            column = columns.get(prop["column_name"])
            if column is None:
                errors.append(
                    {
                        "code": "unknown_column",
                        "message": f"Property {prop['api_name']} maps to column {prop['column_name']} which does not exist on {dataset['name']}",
                    }
                )
                continue
            sql_type = normalize_sql_type(column.get("data_type"))
            if sql_type is None:
                warnings.append(f"Column {prop['column_name']} has no catalog type; skipping type check for {prop['api_name']}")
                continue
            compatible = VALUE_TYPES[prop["value_type"]]["sql_types"]
            if sql_type not in compatible:
                errors.append(
                    {
                        "code": "type_mismatch",
                        "message": f"Property {prop['api_name']} declares value type {prop['value_type']} but column {prop['column_name']} is {sql_type}",
                    }
                )

        mapped_object_names = {row["object_api_name"] for row in self.list_mappings()}
        for link in mapping["links"]:
            if link["target_object_api_name"] not in mapped_object_names:
                errors.append(
                    {
                        "code": "broken_link",
                        "message": f"Link {link['api_name']} targets object type {link['target_object_api_name']} which has no mapping",
                    }
                )
            if link["source_property"] not in property_names:
                errors.append(
                    {
                        "code": "broken_link",
                        "message": f"Link {link['api_name']} uses source property {link['source_property']} which is not defined",
                    }
                )

        interfaces = {row["api_name"]: row for row in self.list_interfaces()}
        declared_value_types = {prop["api_name"]: prop["value_type"] for prop in mapping["properties"]}
        for interface_name in mapping["interfaces"]:
            interface = interfaces.get(interface_name)
            if interface is None:
                errors.append(
                    {
                        "code": "unknown_interface",
                        "message": f"Mapping declares interface {interface_name} which does not exist",
                    }
                )
                continue
            for interface_property in interface["properties"]:
                if not interface_property.get("required", True):
                    continue
                if interface_property["api_name"] not in property_names:
                    errors.append(
                        {
                            "code": "missing_interface_property",
                            "message": f"Interface {interface_name} requires property {interface_property['api_name']}",
                        }
                    )
                elif declared_value_types[interface_property["api_name"]] != interface_property["value_type"]:
                    errors.append(
                        {
                            "code": "type_mismatch",
                            "message": f"Interface {interface_name} requires {interface_property['api_name']} as {interface_property['value_type']}",
                        }
                    )

        for prop in mapping["properties"]:
            if not prop.get("description"):
                warnings.append(f"Property {prop['api_name']} has no description from mapping or dbt docs")

        validation = {
            "mapping_id": mapping_id,
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
        }
        self._execute(
            "UPDATE object_mappings SET validation = ?, updated_at = ? WHERE id = ?",
            (to_json(validation), utc_now(), mapping_id),
        )
        return validation

    def promote_mapping(self, mapping_id: str, payload: PromotionRequest, context: RequestContext) -> dict[str, Any]:
        if payload.validation_status not in {"passed", "approved"}:
            raise ValueError("Mapping promotion requires passed or approved validation status")
        validation = self.validate_mapping(mapping_id)
        if not validation["valid"]:
            codes = sorted({issue["code"] for issue in validation["errors"]})
            raise ValueError(f"Object mapping validation failed: {', '.join(codes)}")
        mapping = self.get_mapping(mapping_id)
        dataset = self.get_dataset(mapping["project_id"], mapping["model_unique_id"])
        project = self.get_project(mapping["project_id"])

        registry_payload = {
            "target": self.settings.object_registry_url,
            "object_type": {
                "api_name": mapping["object_api_name"],
                "display_name": mapping["display_name"],
                "description": mapping["description"],
                "primary_key_property": mapping["primary_key_property"],
                "status": "active",
                "properties": [
                    {
                        "api_name": prop["api_name"],
                        "source_column_name": prop["column_name"],
                        "data_type": prop["value_type"],
                        "required": prop["required"],
                        "description": prop["description"],
                    }
                    for prop in mapping["properties"]
                ],
            },
            "dataset_table": {
                "physical_name": f"{dataset['database']}.{dataset['schema_name']}.{dataset['identifier']}",
                "source": "dbt",
                "project": project["name"],
                "model_unique_id": mapping["model_unique_id"],
                "materialization": dataset["materialization"],
            },
            "link_types": mapping["links"],
            "interfaces": mapping["interfaces"],
        }
        lineage_event = {
            "eventType": "COMPLETE",
            "eventTime": utc_now(),
            "producer": "https://github.com/cognimesh/cognimesh/services/semantic-control",
            "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
            "run": {
                "runId": new_id("promo"),
                "facets": {
                    "cognimesh": {
                        "actor": context.actor,
                        "purpose": context.purpose,
                        "project_id": project["id"],
                        "mapping_id": mapping_id,
                        "action": "object_mapping_promotion",
                    }
                },
            },
            "job": {"namespace": "cognimesh.semantic", "name": mapping["object_api_name"]},
            "inputs": [
                {
                    "namespace": f"{dataset['database']}.{dataset['schema_name']}",
                    "name": dataset["identifier"],
                    "facets": {"unique_id": mapping["model_unique_id"]},
                }
            ],
            "outputs": [
                {
                    "namespace": "cognimesh.objects",
                    "name": mapping["object_api_name"],
                    "facets": {"mapping_id": mapping_id},
                }
            ],
        }
        self._execute(
            """
            UPDATE object_mappings
            SET status = 'active', registry_payload = ?, lineage_event = ?, promoted_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (to_json(registry_payload), to_json(lineage_event), utc_now(), utc_now(), mapping_id),
        )
        return self.get_mapping(mapping_id)

    # ------------------------------------------------------------------ catalog sync

    def sync_catalog(self, payload: CatalogSyncRequest) -> dict[str, Any]:
        datasets = self.list_datasets()
        mappings = self.list_mappings()
        contracts = self.list_contracts()
        entities = {
            "datasets": len(datasets),
            "object_mappings": len(mappings),
            "contracts": len(contracts),
            "dataset_unique_ids": sorted(dataset["unique_id"] for dataset in datasets),
            "object_api_names": sorted(mapping["object_api_name"] for mapping in mappings),
        }
        if payload.target == "datahub" and not self.settings.datahub_enabled:
            status = "planned"
            entities["emitter"] = {"gms_url": self.settings.datahub_gms_url, "enabled": False}
        else:
            status = "completed"
        sync_id = new_id("csync")
        self._execute(
            "INSERT INTO catalog_syncs (id, target, status, entities, created_at) VALUES (?, ?, ?, ?, ?)",
            (sync_id, payload.target, status, to_json(entities), utc_now()),
        )
        return self._fetch_one("SELECT * FROM catalog_syncs WHERE id = ?", (sync_id,))

    def integrations_config(self) -> dict[str, Any]:
        return {
            "supported_artifacts": ["manifest.json", "catalog.json", "run_results.json"],
            "dbt_adapters": ["duckdb", "postgres", "trino", "spark"],
            "contract_types": ["not_null", "unique", "accepted_values", "relationship_integrity", "custom"],
            "object_registry_url": self.settings.object_registry_url,
            "pipeline_control_url": self.settings.pipeline_control_url,
            "lineage_endpoint_url": self.settings.lineage_endpoint_url,
            "local_catalog": {"enabled": True},
            "datahub": {"gms_url": self.settings.datahub_gms_url, "default_enabled": self.settings.datahub_enabled},
        }


_repository: SemanticRepository | None = None
_repository_path: str | None = None


def get_repository() -> SemanticRepository:
    global _repository, _repository_path
    settings = get_settings()
    if _repository is None or _repository_path != settings.state_path:
        if _repository is not None:
            _repository.close()
        _repository = SemanticRepository(settings)
        _repository_path = settings.state_path
    return _repository


def reset_repository() -> None:
    global _repository, _repository_path
    if _repository is not None:
        _repository.close()
    _repository = None
    _repository_path = None
