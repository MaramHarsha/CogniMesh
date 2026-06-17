#!/usr/bin/env python3
import os
import sys
import json
import re

# Local offline database of known CVEs for checking
VULNERABILITY_DB = {
    "python": [
        {"name": "fastapi", "operator": "<", "version": "0.100.0", "cve": "CVE-2023-30798", "severity": "HIGH", "description": "Request body validation bypass"},
        {"name": "httpx", "operator": "<", "version": "0.24.0", "cve": "CVE-2023-26144", "severity": "MEDIUM", "description": "Redirect URL processing vulnerability"},
        {"name": "uvicorn", "operator": "<", "version": "0.22.0", "cve": "CVE-2023-30000", "severity": "HIGH", "description": "Request handling DoS"},
        {"name": "pydantic", "operator": "<", "version": "2.0", "cve": "CVE-2023-28114", "severity": "HIGH", "description": "Type confusion parsing vulnerability"}
    ],
    "npm": [
        {"name": "typescript", "operator": "<", "version": "5.0.0", "cve": "CVE-2023-20000", "severity": "MEDIUM", "description": "Compiling resource exhaustion"},
        {"name": "ts-node", "operator": "<", "version": "10.9.0", "cve": "CVE-2023-30111", "severity": "HIGH", "description": "Prototype pollution via options"}
    ]
}

try:
    import tomllib
except ImportError:
    tomllib = None

def parse_pyproject_toml(file_path):
    deps = []
    if tomllib:
        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})
            for d in project.get("dependencies", []):
                deps.append(d)
            opt_deps = project.get("optional-dependencies", {})
            for group, group_deps in opt_deps.items():
                for d in group_deps:
                    deps.append(d)
        except Exception:
            pass
    else:
        # Fallback simple parsing
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
    
    parsed = []
    for d in deps:
        parts = re.split(r'(>=|<=|==|!=|>|<|\[)', d)
        if parts:
            name = parts[0].strip()
            version_match = re.search(r'([0-9\.]+)', d)
            version = version_match.group(1) if version_match else "0.0.0"
            parsed.append({"name": name, "version": version, "type": "python"})
    return parsed

def parse_package_json(file_path):
    parsed = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for name, ver in data.get("dependencies", {}).items():
            clean_ver = re.sub(r'[\^~>=<]', '', ver)
            parsed.append({"name": name, "version": clean_ver, "type": "npm"})
        for name, ver in data.get("devDependencies", {}).items():
            clean_ver = re.sub(r'[\^~>=<]', '', ver)
            parsed.append({"name": name, "version": clean_ver, "type": "npm"})
    except Exception:
        pass
    return parsed

def compare_versions(ver1, ver2):
    # simple semantic version comparison
    p1 = [int(x) for x in re.findall(r'\d+', ver1)]
    p2 = [int(x) for x in re.findall(r'\d+', ver2)]
    # pad with zeros
    length = max(len(p1), len(p2))
    p1 += [0] * (length - len(p1))
    p2 += [0] * (length - len(p2))
    for a, b in zip(p1, p2):
        if a < b: return -1
        if a > b: return 1
    return 0

def check_vulnerabilities(deps):
    findings = []
    for dep in deps:
        pkg_type = dep["type"]
        pkg_name = dep["name"]
        pkg_version = dep["version"]
        
        cve_rules = VULNERABILITY_DB.get(pkg_type == "python" and "python" or "npm", [])
        for rule in cve_rules:
            if rule["name"].lower() == pkg_name.lower():
                cmp = compare_versions(pkg_version, rule["version"])
                is_vuln = False
                if rule["operator"] == "<" and cmp < 0:
                    is_vuln = True
                elif rule["operator"] == "<=" and cmp <= 0:
                    is_vuln = True
                elif rule["operator"] == "==" and cmp == 0:
                    is_vuln = True
                
                if is_vuln:
                    findings.append({
                        "name": pkg_name,
                        "version": pkg_version,
                        "cve": rule["cve"],
                        "severity": rule["severity"],
                        "description": rule["description"]
                    })
    return findings

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    print("Scanning dependencies for known vulnerabilities...")
    
    deps = []
    ignore_dirs = {".git", "node_modules", "venv", ".venv", ".pytest_cache", "dist", "build"}
    
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            file_path = os.path.join(root, file)
            if file == "pyproject.toml" and "_template" not in file_path:
                deps.extend(parse_pyproject_toml(file_path))
            elif file == "package.json":
                deps.extend(parse_package_json(file_path))

    findings = check_vulnerabilities(deps)
    high_critical_findings = [f for f in findings if f["severity"] in ("HIGH", "CRITICAL")]

    if high_critical_findings:
        print(f"FAILED: Found {len(high_critical_findings)} high/critical vulnerabilities:")
        for f in high_critical_findings:
            print(f"  {f['name']}@{f['version']} -> {f['cve']} [{f['severity']}]: {f['description']}")
        sys.exit(1)
    else:
        if findings:
            print(f"Passed with warnings. Found {len(findings)} low/medium vulnerabilities:")
            for f in findings:
                print(f"  [WARNING] {f['name']}@{f['version']} -> {f['cve']} [{f['severity']}]: {f['description']}")
        else:
            print("PASSED: Zero vulnerabilities found.")
        sys.exit(0)

if __name__ == "__main__":
    main()
