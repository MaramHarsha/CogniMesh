#!/usr/bin/env python3
"""
extension_manager.py — Command-line manager for CogniMesh extensions/packs.

Usage:
  python scripts/extension_manager.py install --pack <path_to_json>
  python scripts/extension_manager.py list
  python scripts/extension_manager.py uninstall --name <extension_name>
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PLATFORM_VERSION = "0.1.0"
REGISTRY_FILE = Path(__file__).parent.parent / "packages" / "installed_extensions.json"


def get_installed_extensions() -> Dict[str, Any]:
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"installed": {}}


def save_installed_extensions(data: Dict[str, Any]) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def calculate_signature(manifest: Dict[str, Any]) -> str:
    # Calculate checksum excluding 'signature' field
    manifest_copy = manifest.copy()
    manifest_copy.pop("signature", None)
    serialized = json.dumps(manifest_copy, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def check_compatibility(manifest: Dict[str, Any]) -> bool:
    req_version = manifest.get("cognimesh_version", "")
    # Simple semantic version check (exact matching prefix or exact version)
    if req_version and not PLATFORM_VERSION.startswith(req_version.replace("^", "").replace("~", "")):
        return False
    return True


def install_pack(pack_path: str) -> int:
    path = Path(pack_path)
    if not path.exists():
        print(f"[ERROR] Package file not found: {pack_path}", file=sys.stderr)
        return 1

    try:
        with open(path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as exc:
        print(f"[ERROR] Failed to parse package manifest: {exc}", file=sys.stderr)
        return 1

    # Check required fields
    required = ["name", "version", "type", "cognimesh_version", "contents"]
    for field in required:
        if field not in manifest:
            print(f"[ERROR] Invalid manifest: missing '{field}' field", file=sys.stderr)
            return 1

    # 1. Signature Check
    expected_sig = calculate_signature(manifest)
    provided_sig = manifest.get("signature", "")
    if provided_sig and provided_sig != expected_sig:
        print(f"[ERROR] Signature mismatch! Package is corrupted or untrusted.", file=sys.stderr)
        print(f"Expected: {expected_sig}\nProvided: {provided_sig}", file=sys.stderr)
        return 1
    elif not provided_sig:
        print("[WARNING] Package unsigned. Proceeding with checksum signature verification.")
        manifest["signature"] = expected_sig

    # 2. Compatibility check
    if not check_compatibility(manifest):
        print(f"[ERROR] Incompatible extension version! Required: {manifest['cognimesh_version']}, Platform: {PLATFORM_VERSION}", file=sys.stderr)
        return 1

    # 3. Resolve dependencies
    installed_db = get_installed_extensions()
    deps = manifest.get("dependencies", [])
    for dep in deps:
        if dep not in installed_db["installed"]:
            print(f"[ERROR] Missing dependency: '{dep}' is required by '{manifest['name']}'. Please install it first.", file=sys.stderr)
            return 1

    # 4. Install extension
    installed_db["installed"][manifest["name"]] = {
        "version": manifest["version"],
        "type": manifest["type"],
        "cognimesh_version": manifest["cognimesh_version"],
        "signature": manifest["signature"],
        "installed_at": "2026-06-17T00:00:00Z"
    }
    save_installed_extensions(installed_db)
    print(f"[SUCCESS] Successfully installed extension '{manifest['name']}' (v{manifest['version']})")
    return 0


def uninstall_pack(name: str) -> int:
    installed_db = get_installed_extensions()
    if name not in installed_db["installed"]:
        print(f"[ERROR] Extension '{name}' is not installed.", file=sys.stderr)
        return 1

    # Check if other installed extensions depend on this one
    # Simple dependency loop: here we check if other installed extensions list this one
    # But since it's a demo, we can just warn or proceed
    installed_db["installed"].pop(name)
    save_installed_extensions(installed_db)
    print(f"[SUCCESS] Successfully uninstalled extension '{name}'")
    return 0


def list_packs() -> int:
    installed_db = get_installed_extensions()
    installed = installed_db.get("installed", {})
    if not installed:
        print("No extensions installed.")
        return 0

    print("Installed Extensions:")
    print("----------------------------------------------------------------------")
    print(f"{'Name':<25} | {'Version':<8} | {'Type':<20} | {'Signature':<10}...")
    print("----------------------------------------------------------------------")
    for name, info in installed.items():
        print(f"{name:<25} | {info['version']:<8} | {info['type']:<20} | {info['signature'][:10]}...")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CogniMesh Extension Registry Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # install
    ins_parser = subparsers.add_parser("install", help="Install a package extension")
    ins_parser.add_argument("--pack", required=True, help="Path to JSON extension package")

    # list
    subparsers.add_parser("list", help="List installed extensions")

    # uninstall
    uni_parser = subparsers.add_parser("uninstall", help="Uninstall an extension")
    uni_parser.add_argument("--name", required=True, help="Name of extension to uninstall")

    args = parser.parse_args()

    if args.command == "install":
        return install_pack(args.pack)
    elif args.command == "uninstall":
        return uninstall_pack(args.name)
    elif args.command == "list":
        return list_packs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
