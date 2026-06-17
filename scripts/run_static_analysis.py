#!/usr/bin/env python3
import os
import re
import sys

# High-risk patterns in code
SECURITY_RULES = [
    {
        "name": "Unsafe Eval Execution",
        "pattern": re.compile(r"\beval\s*\("),
        "severity": "HIGH",
        "description": "Dynamic evaluation using eval() is insecure."
    },
    {
        "name": "Unsafe Exec Execution",
        "pattern": re.compile(r"\bexec\s*\("),
        "severity": "HIGH",
        "description": "Dynamic execution using exec() is insecure."
    },
    {
        "name": "Shell Injection Risk",
        "pattern": re.compile(r"shell\s*=\s*True"),
        "severity": "HIGH",
        "description": "Running subprocess with shell=True is vulnerable to shell injection."
    },
    {
        "name": "Raw SQL Concatenation",
        "pattern": re.compile(r"\.execute\(\s*f?[\"']SELECT\s+.*\{.*\}"),
        "severity": "HIGH",
        "description": "SQL query executed with f-string formatting risks SQL injection."
    }
]

EXCLUDE_DIRS = {".git", "node_modules", "venv", ".venv", ".pytest_cache", "dist", "build"}
EXCLUDE_FILES = {"run_static_analysis.py", "validate_module21.py", "validate_module22.py", "validate_module23.py", "validate_module24.py", "validate_e2e_scenarios.py"}

def scan_file(file_path):
    findings = []
    if os.path.basename(file_path) in EXCLUDE_FILES:
        return findings
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                # Ignore comment lines or lines with explicit exclusion comments
                if line.strip().startswith("#") or "# noqa" in line or "# safe" in line:
                    continue
                for rule in SECURITY_RULES:
                    if rule["pattern"].search(line):
                        findings.append({
                            "file": file_path,
                            "line": idx,
                            "rule": rule["name"],
                            "severity": rule["severity"],
                            "description": rule["description"],
                            "content": line.strip()[:100]
                        })
    except Exception:
        pass
    return findings

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    print("Running static security analysis...")
    
    all_findings = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                all_findings.extend(scan_file(file_path))
                
    high_findings = [f for f in all_findings if f["severity"] == "HIGH"]
    if high_findings:
        print(f"FAILED: Found {len(high_findings)} high-severity static analysis issues:")
        for f in high_findings:
            print(f"  {f['file']}:{f['line']} [{f['rule']}] -> {f['content']}")
            print(f"    Description: {f['description']}")
        sys.exit(1)
    else:
        print("PASSED: No static analysis issues found.")
        sys.exit(0)

if __name__ == "__main__":
    main()
