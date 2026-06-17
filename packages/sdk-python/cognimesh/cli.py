from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from cognimesh.client import CogniMeshClient

CONFIG_DIR = Path.home() / ".cognimesh"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_client(config: dict[str, Any]) -> CogniMeshClient:
    return CogniMeshClient(
        query_service_url=config.get("query_service_url"),
        app_control_url=config.get("app_control_url"),
        object_registry_url=config.get("object_registry_url"),
        action_control_url=config.get("action_control_url"),
        pipeline_control_url=config.get("pipeline_control_url"),
        governance_control_url=config.get("governance_control_url"),
        actor=config.get("actor"),
        roles=config.get("roles"),
        purpose=config.get("purpose"),
        workspace_id=config.get("workspace_id"),
    )


def handle_login(args: argparse.Namespace) -> int:
    config = load_config()
    if args.actor is not None:
        config["actor"] = args.actor
    if args.roles is not None:
        config["roles"] = [r.strip() for r in args.roles.split(",") if r.strip()]
    if args.purpose is not None:
        config["purpose"] = args.purpose
    save_config(config)
    print("Login credentials saved:")
    print(json.dumps(config, indent=2))
    return 0


def handle_workspace(args: argparse.Namespace) -> int:
    config = load_config()
    if args.id is not None:
        config["workspace_id"] = args.id
        save_config(config)
        print(f"Workspace set to: {args.id}")
    else:
        current = config.get("workspace_id")
        if current:
            print(f"Current workspace: {current}")
        else:
            print("No workspace configured.")
    return 0


def handle_register(args: argparse.Namespace) -> int:
    config = load_config()
    client = get_client(config)
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        print(f"Error reading schema file: {exc}", file=sys.stderr)
        return 1

    try:
        result = client.register_object_type(payload)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f"Error registering object type: {exc}", file=sys.stderr)
        return 1


def handle_query(args: argparse.Namespace) -> int:
    config = load_config()
    client = get_client(config)
    
    # build where dictionary
    where_dict = {}
    if args.where:
        for item in args.where:
            if "=" in item:
                k, v = item.split("=", 1)
                where_dict[k] = v

    payload: dict[str, Any] = {
        "from": args.object_type,
        "select": args.select.split(",") if args.select else [],
        "where": where_dict,
        "offset": args.offset,
    }
    if args.limit is not None:
        payload["limit"] = args.limit

    try:
        result = client.execute_query(payload)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f"Error executing query: {exc}", file=sys.stderr)
        return 1


def handle_lineage(args: argparse.Namespace) -> int:
    config = load_config()
    client = get_client(config)
    try:
        if args.graph:
            result = client.get_lineage_graph(args.kind, args.id)
        else:
            result = client.get_lineage(args.kind, args.id)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f"Error retrieving lineage: {exc}", file=sys.stderr)
        return 1


def handle_pipeline(args: argparse.Namespace) -> int:
    config = load_config()
    client = get_client(config)
    try:
        if args.pipeline_cmd == "run":
            run_payload = {}
            if args.file:
                with open(args.file, "r", encoding="utf-8") as f:
                    run_payload = json.load(f)
            result = client.run_pipeline(args.id, run_payload)
            print(json.dumps(result, indent=2))
        elif args.pipeline_cmd == "status":
            result = client.get_pipeline_run(args.id)
            print(json.dumps(result, indent=2))
        else:
            print("Invalid pipeline command.", file=sys.stderr)
            return 1
        return 0
    except Exception as exc:
        print(f"Error during pipeline operation: {exc}", file=sys.stderr)
        return 1


def handle_app(args: argparse.Namespace) -> int:
    config = load_config()
    client = get_client(config)
    try:
        if args.app_cmd == "register":
            deps = [d.strip() for d in args.dependencies.split(",") if d.strip()] if args.dependencies else []
            result = client.register_app(
                name=args.name,
                workspace_id=args.workspace or config.get("workspace_id", "default"),
                purpose=args.purpose or config.get("purpose", "analytics"),
                owner=args.owner or config.get("actor", "system"),
                data_dependencies=deps,
                deployment_url=args.deployment_url,
            )
            print(json.dumps(result, indent=2))
        elif args.app_cmd == "list":
            ws = args.workspace or config.get("workspace_id")
            result = client.list_apps(workspace_id=ws)
            print(json.dumps(result, indent=2))
        elif args.app_cmd == "deploy":
            result = client.deploy_app(args.id, environment=args.env)
            print(json.dumps(result, indent=2))
        else:
            print("Invalid app command.", file=sys.stderr)
            return 1
        return 0
    except Exception as exc:
        print(f"Error during app operation: {exc}", file=sys.stderr)
        return 1


def handle_policy(args: argparse.Namespace) -> int:
    config = load_config()
    client = get_client(config)
    try:
        if args.policy_cmd == "simulate":
            # Simulate endpoint: hit governance service if needed
            url = f"{client.governance_control_url}/v1/governance/policies/simulate"
            payload = {}
            if args.file:
                with open(args.file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            res = client._http_client.post(url, json=payload, headers=client.get_headers())
            res.raise_for_status()
            print(json.dumps(res.json(), indent=2))
        elif args.policy_cmd == "list":
            url = f"{client.governance_control_url}/v1/governance/policies"
            res = client._http_client.get(url, headers=client.get_headers())
            res.raise_for_status()
            print(json.dumps(res.json(), indent=2))
        else:
            print("Invalid policy command.", file=sys.stderr)
            return 1
        return 0
    except Exception as exc:
        print(f"Error during policy operation: {exc}", file=sys.stderr)
        return 1


def handle_extension(args: argparse.Namespace) -> int:
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))
    try:
        import extension_manager
        if args.extension_cmd == "install":
            return extension_manager.install_pack(args.pack)
        elif args.extension_cmd == "uninstall":
            return extension_manager.uninstall_pack(args.name)
        elif args.extension_cmd == "list":
            return extension_manager.list_packs()
    except Exception as exc:
        print(f"Error executing extension command: {exc}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CogniMesh Command Line Interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # login
    login_parser = subparsers.add_parser("login", help="Set user session credentials")
    login_parser.add_argument("--actor", help="User actor identifier")
    login_parser.add_argument("--roles", help="Comma-separated roles")
    login_parser.add_argument("--purpose", help="Default purpose context")

    # workspace
    ws_parser = subparsers.add_parser("workspace", help="Get or set the active workspace")
    ws_parser.add_argument("--id", help="Active workspace ID to set")

    # register
    reg_parser = subparsers.add_parser("register", help="Register an object type schema file")
    reg_parser.add_argument("--file", required=True, help="Path to JSON file containing ObjectTypeCreate payload")

    # query
    query_parser = subparsers.add_parser("query", help="Query objects from Object Query Service")
    query_parser.add_argument("--from", dest="object_type", required=True, help="Object type name")
    query_parser.add_argument("--select", help="Comma-separated properties to select")
    query_parser.add_argument("--where", action="append", help="Filter conditions in key=val format")
    query_parser.add_argument("--limit", type=int, help="Limit number of results")
    query_parser.add_argument("--offset", type=int, default=0, help="Offset results")

    # lineage
    lin_parser = subparsers.add_parser("lineage", help="Inspect lineage for a specific asset")
    lin_parser.add_argument("--kind", required=True, help="Asset kind (e.g. object_type, dataset_table)")
    lin_parser.add_argument("--id", required=True, help="Asset ID")
    lin_parser.add_argument("--graph", action="store_true", help="Retrieve interactive lineage graph instead of events")

    # pipeline
    pipe_parser = subparsers.add_parser("pipeline", help="Manage pipeline execution")
    pipe_sub = pipe_parser.add_subparsers(dest="pipeline_cmd", required=True)
    pipe_run = pipe_sub.add_parser("run", help="Run a pipeline")
    pipe_run.add_argument("--id", required=True, help="Pipeline ID")
    pipe_run.add_argument("--file", help="Path to JSON run parameters")
    pipe_status = pipe_sub.add_parser("status", help="Get pipeline run status")
    pipe_status.add_argument("--id", required=True, help="Pipeline run ID")

    # app
    app_parser = subparsers.add_parser("app", help="Manage application registry")
    app_sub = app_parser.add_subparsers(dest="app_cmd", required=True)
    app_reg = app_sub.add_parser("register", help="Register a new application")
    app_reg.add_argument("--name", required=True, help="App name")
    app_reg.add_argument("--workspace", help="Workspace ID (defaults to active workspace)")
    app_reg.add_argument("--purpose", help="App purpose (defaults to active purpose)")
    app_reg.add_argument("--owner", help="Owner username")
    app_reg.add_argument("--dependencies", help="Comma-separated data dependencies")
    app_reg.add_argument("--deployment-url", help="URL of deployed application")
    app_list = app_sub.add_parser("list", help="List registered applications")
    app_list.add_argument("--workspace", help="Filter apps by workspace")
    app_deploy = app_sub.add_parser("deploy", help="Deploy/activate a registered app")
    app_deploy.add_argument("--id", required=True, help="App ID")
    app_deploy.add_argument("--env", default="production", help="Deployment environment")

    # policy
    pol_parser = subparsers.add_parser("policy", help="Manage and simulate policies")
    pol_sub = pol_parser.add_subparsers(dest="policy_cmd", required=True)
    pol_sim = pol_sub.add_parser("simulate", help="Simulate a policy decision")
    pol_sim.add_argument("--file", required=True, help="Path to JSON policy simulation input")
    pol_list = pol_sub.add_parser("list", help="List active policies")

    # extension
    ext_parser = subparsers.add_parser("extension", help="Manage marketplace extensions")
    ext_sub = ext_parser.add_subparsers(dest="extension_cmd", required=True)
    ext_inst = ext_sub.add_parser("install", help="Install a package pack")
    ext_inst.add_argument("--pack", required=True, help="Path to JSON package file")
    ext_list = ext_sub.add_parser("list", help="List installed extension packs")
    ext_uninst = ext_sub.add_parser("uninstall", help="Uninstall an extension")
    ext_uninst.add_argument("--name", required=True, help="Name of extension pack")

    args = parser.parse_args()

    handlers = {
        "login": handle_login,
        "workspace": handle_workspace,
        "register": handle_register,
        "query": handle_query,
        "lineage": handle_lineage,
        "pipeline": handle_pipeline,
        "app": handle_app,
        "policy": handle_policy,
        "extension": handle_extension,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
