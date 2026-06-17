#!/usr/bin/env python3
import os
import json
import re

try:
    import tomllib
except ImportError:
    # Fallback to simple parser if tomllib is not available on some older systems
    tomllib = None

def parse_pyproject_toml(file_path):
    deps = []
    if tomllib:
        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)
            # Standard dependencies
            project = data.get("project", {})
            for d in project.get("dependencies", []):
                deps.append(d)
            # Optional dependencies
            opt_deps = project.get("optional-dependencies", {})
            for group, group_deps in opt_deps.items():
                for d in group_deps:
                    deps.append(d)
        except Exception:
            pass
    else:
        # Simple regex extraction for fallback compatibility
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # extract string literals in arrays
            matches = re.findall(r'"([^"]+)"|\'([^\']+)\'', content)
            for m in matches:
                val = m[0] or m[1]
                if (">=" in val or "==" in val or "<" in val) and not val.startswith("-"):
                    deps.append(val)
        except Exception:
            pass
    
    parsed_deps = []
    for dep in deps:
        # Split on operator
        parts = re.split(r'(>=|<=|==|!=|>|<|\[)', dep)
        if parts:
            name = parts[0].strip()
            version_match = re.search(r'([0-9\.]+)', dep)
            version = version_match.group(1) if version_match else "unknown"
            parsed_deps.append({"name": name, "version": version, "type": "python"})
    return parsed_deps

def parse_package_json(file_path):
    parsed_deps = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for name, ver in data.get("dependencies", {}).items():
            clean_ver = re.sub(r'[\^~>=<]', '', ver)
            parsed_deps.append({"name": name, "version": clean_ver, "type": "npm"})
        for name, ver in data.get("devDependencies", {}).items():
            clean_ver = re.sub(r'[\^~>=<]', '', ver)
            parsed_deps.append({"name": name, "version": clean_ver, "type": "npm"})
    except Exception:
        pass
    return parsed_deps

def generate_sbom(root_dir, output_path):
    components = []
    seen = set()

    ignore_dirs = {".git", "node_modules", "venv", ".venv", ".pytest_cache", "dist", "build"}

    for root, dirs, files in os.walk(root_dir):
        # In-place directory filtering
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            if file == "pyproject.toml":
                # Skip template folders if any
                if "_template" in file_path:
                    continue
                file_deps = parse_pyproject_toml(file_path)
                for d in file_deps:
                    key = (d["name"], d["version"], d["type"])
                    if key not in seen:
                        seen.add(key)
                        components.append(d)
            elif file == "package.json":
                file_deps = parse_package_json(file_path)
                for d in file_deps:
                    key = (d["name"], d["version"], d["type"])
                    if key not in seen:
                        seen.add(key)
                        components.append(d)

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:790103ee-19de-43a9-ae9b-09029ddb9224",
        "version": 1,
        "metadata": {
            "component": {
                "name": "cognimesh",
                "version": "0.1.0",
                "type": "application"
            }
        },
        "components": []
    }

    for comp in components:
        purl_type = "pip" if comp["type"] == "python" else "npm"
        sbom["components"].append({
            "type": "library",
            "name": comp["name"],
            "version": comp["version"],
            "purl": f"pkg:{purl_type}/{comp['name']}@{comp['version']}"
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sbom, f, indent=2)
    
    print(f"SBOM successfully generated with {len(components)} components at {output_path}")
    return len(components)

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    output_path = os.path.join(root_dir, "cognimesh-sbom.json")
    generate_sbom(root_dir, output_path)
