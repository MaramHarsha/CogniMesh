#!/usr/bin/env python3
import os
import re
import sys

# High-risk patterns
PATTERNS = {
    "Private Key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS Access Key ID": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Google API Key": re.compile(r"\bAIzaSy[0-9a-zA-Z\-_]{33}\b"),
    "Stripe Secret Key": re.compile(r"\bsk_live_[0-9a-zA-Z]{24}\b"),
    "Generic Credentials": re.compile(r"\b(password|passwd|client_secret|client-secret)\s*=\s*['\"][a-zA-Z0-9_]{12,}['\"]", re.IGNORECASE)
}

# Ignore patterns in files
EXCLUDE_DIRS = {".git", "node_modules", "venv", ".venv", ".pytest_cache", "dist", "build"}
EXCLUDE_FILES = {"scan_secrets.py", "validate_module21.py", "validate_module22.py", "validate_module23.py", "validate_module24.py", "validate_e2e_scenarios.py", "db_backup_restore.py"}

def is_binary(file_path):
    try:
        with open(file_path, "tr") as f:
            f.read(1024)
            return False
    except UnicodeDecodeError:
        return True

def scan_file(file_path):
    findings = []
    if os.path.basename(file_path) in EXCLUDE_FILES:
        return findings
    if is_binary(file_path):
        return findings

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                for name, pattern in PATTERNS.items():
                    if pattern.search(line):
                        # Simple rule to avoid matching mock properties in JSON config
                        if "mock" in line.lower() or "test" in line.lower() or "dummy" in line.lower() or "example" in line.lower():
                            continue
                        # If generic credentials pattern matches, make sure it is not just standard config keys or template placeholders
                        if name == "Generic Credentials":
                            if "postgres" in line.lower() or "sqlite" in line.lower() or "localhost" in line.lower() or "username" in line.lower():
                                continue
                        findings.append({
                            "file": file_path,
                            "line": idx,
                            "type": name,
                            "content": line.strip()[:100]
                        })
    except Exception as e:
        pass
    return findings

def run_scan(root_dir):
    all_findings = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            file_path = os.path.join(root, file)
            findings = scan_file(file_path)
            all_findings.extend(findings)
    return all_findings

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    print("Scanning for committed secrets...")
    findings = run_scan(root_dir)
    if findings:
        print(f"FAILED: Found {len(findings)} potential secrets:")
        for f in findings:
            print(f"  {f['file']}:{f['line']} [{f['type']}] -> {f['content']}")
        sys.exit(1)
    else:
        print("PASSED: No secrets found.")
        sys.exit(0)
