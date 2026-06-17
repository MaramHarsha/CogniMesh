#!/usr/bin/env python3
"""
run_demo.py — End-to-end demo runner for CogniMesh.
Shows how a developer uses the Python SDK to register types, submit actions, query objects, log audits, and inspect lineage.

Usage:
  python examples/run_demo.py [--dry-run]
"""
import argparse
import sys


def run_demo(client) -> None:
    print("\n[1] Registering reference Employee Schema...")
    schema = {
        "namespace_id": "hr_domain",
        "api_name": "Employee",
        "display_name": "Employee Profile",
        "description": "Semantic model for employee profile records",
        "primary_key_property": "id",
        "status": "active",
        "allowed_purposes": ["payroll", "analytics"],
        "classification_tags": ["PII"],
        "default_access": "read_metadata"
    }
    reg_res = client.register_object_type(schema)
    print(f"  -> Object Type Registered. ID: {reg_res.get('id', 'obj_employee')}")

    print("\n[2] Submitting action to create a new Employee object...")
    action = {
        "action_type": "create_employee",
        "object_id": "emp_006",
        "parameters": {
            "first_name": "David",
            "last_name": "Miller",
            "salary": 140000,
            "status": "ACTIVE"
        }
    }
    action_res = client.submit_action(action)
    print(f"  -> Action Submission Status: {action_res.get('status', 'applied')} (Submission ID: {action_res.get('id', 'sub_987')})")

    print("\n[3] Executing Fluent Object Query...")
    query_builder = (
        client.objects("Employee")
        .select("id", "first_name", "salary")
        .where("status", "ACTIVE")
        .where("salary", gte=100000)
    )
    print(f"  Generated payload:\n  {query_builder.to_dict()}")
    query_res = query_builder.execute()
    print(f"  -> Query succeeded. Row count: {query_res.get('row_count', 2)}")
    for row in query_res.get("rows", []):
        print(f"     * {row['id']}: {row.get('first_name', 'Unknown')} (${row.get('salary', 0):,})" if 'salary' in row else f"     * {row['id']}: {row.get('first_name', 'Unknown')}")

    print("\n[4] Logging Application Audit log...")
    audit_res = client.log_audit(
        app_id="capp_dashboard_01",
        user_id=getattr(client, "actor", None) or "demo_user",
        operation="READ",
        asset_id="Employee",
        purpose=getattr(client, "purpose", None) or "analytics",
        details={"query": "active_high_salary_employees"}
    )
    print(f"  -> Audit event recorded. ID: {audit_res.get('id', 'aud_111')}")

    print("\n[5] Inspecting lineage records for Employee object type...")
    lineage_res = client.get_lineage("object_type", "Employee")
    print(f"  -> Retrieved {len(lineage_res)} lineage event(s):")
    for event in lineage_res:
        print(f"     * Event ID: {event.get('id', 'evt_abc')} | Producer: {event.get('producer', 'cognimesh://manual')} | Job: {event.get('job_name', 'load_employee_seed')}")


class DummyQueryBuilder:
    def __init__(self, object_type: str):
        self._object_type = object_type

    def select(self, *args):
        return self

    def where(self, *args, **kwargs):
        return self

    def to_dict(self):
        return {
            "from": self._object_type,
            "select": ["id", "first_name", "salary"],
            "where": {"status": "ACTIVE", "salary": {"gte": 100000}},
            "offset": 0
        }

    def execute(self):
        return {
            "row_count": 2,
            "rows": [
                {"id": "emp_001", "first_name": "John", "salary": 120000},
                {"id": "emp_006", "first_name": "David", "salary": 140000}
            ]
        }


class DummyClient:
    def __init__(self):
        self.actor = "demo_dev"
        self.purpose = "analytics"

    def register_object_type(self, schema):
        return {"id": "obj_employee", "status": "active"}

    def submit_action(self, action):
        return {"id": "sub_987", "status": "applied"}

    def objects(self, object_type: str):
        return DummyQueryBuilder(object_type)

    def log_audit(self, **kwargs):
        return {"id": "aud_111"}

    def get_lineage(self, kind, id):
        return [
            {"id": "evt_abc", "producer": "cognimesh://manual", "job_name": "load_employee_seed"}
        ]


def main():
    parser = argparse.ArgumentParser(description="CogniMesh Demo Runner")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run in mock dry-run mode (default)")
    parser.add_argument("--real", action="store_false", dest="dry_run", help="Connect to actual running local services")

    args = parser.parse_args()

    if args.dry_run:
        print("--- Running Demo in DRY-RUN Mock Mode ---")
        client = DummyClient()
        run_demo(client)
    else:
        print("--- Running Demo connecting to Local Services ---")
        from cognimesh.client import CogniMeshClient
        client = CogniMeshClient(
            actor="demo_dev",
            roles=["platform_admin"],
            purpose="analytics",
            workspace_id="default"
        )
        try:
            run_demo(client)
        except Exception as exc:
            print(f"\n[ERROR] Real run failed: {exc}", file=sys.stderr)
            print("Make sure Docker Compose services are running and ports are open.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
