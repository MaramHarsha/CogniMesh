#!/usr/bin/env python3
import os
import sys
import subprocess

def check_file_exists(path):
    if not os.path.exists(path):
        print(f"FAILED: Required security document is missing: {path}")
        return False
    # Check if not empty
    if os.path.getsize(path) < 100:
        print(f"FAILED: Security document is empty or too small: {path}")
        return False
    print(f"PASSED: Found and verified: {path}")
    return True

def run_script(script_name, cwd):
    script_path = os.path.join(cwd, "scripts", script_name)
    print(f"Executing: python {script_path}")
    res = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED: {script_name} returned non-zero exit code {res.returncode}")
        print("STDOUT:")
        print(res.stdout)
        print("STDERR:")
        print(res.stderr)
        return False
    print(f"PASSED: {script_name} finished successfully.")
    return True

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    print("==================================================")
    # 1. Check Security Documentation
    docs = [
        os.path.join(root_dir, "docs", "operations", "security", "threat_model.md"),
        os.path.join(root_dir, "docs", "operations", "security", "secure_defaults.md"),
        os.path.join(root_dir, "docs", "operations", "security", "release_certification_guidelines.md")
    ]
    
    docs_ok = True
    for d in docs:
        if not check_file_exists(d):
            docs_ok = False
            
    if not docs_ok:
        sys.exit(1)
        
    print("==================================================")
    # 2. Run Security Tools
    tools = [
        "generate_sbom.py",
        "scan_secrets.py",
        "scan_dependencies.py",
        "run_static_analysis.py",
        "dynamic_security_test.py"
    ]
    
    tools_ok = True
    for t in tools:
        if not run_script(t, root_dir):
            tools_ok = False
            
    if not tools_ok:
        sys.exit(1)
        
    # 3. Check that SBOM is published
    sbom_path = os.path.join(root_dir, "cognimesh-sbom.json")
    if not os.path.exists(sbom_path):
        print("FAILED: SBOM file was not published at the workspace root.")
        sys.exit(1)
        
    print("==================================================")
    print("PASSED — Module 24 acceptance criteria met.")
    sys.exit(0)

if __name__ == "__main__":
    main()
