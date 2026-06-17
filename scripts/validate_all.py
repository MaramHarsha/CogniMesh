#!/usr/bin/env python3
import os
import sys
import subprocess
import re

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Discover all validate_ scripts
    scripts = []
    for file in os.listdir(script_dir):
        if file.startswith("validate_") and file.endswith(".py") and file != "validate_all.py":
            scripts.append(file)
            
    # Custom sort: foundation first, then modules 1-24 numerically, then e2e_scenarios last
    def sort_key(filename):
        if "foundation" in filename:
            return -1
        if "e2e_scenarios" in filename:
            return 9999
        match = re.search(r'module(\d+)', filename)
        if match:
            return int(match.group(1))
        return 1000
        
    scripts.sort(key=sort_key)
    
    # Avoid PermissionError on Windows by using a local basetemp and disabling cache
    env = os.environ.copy()
    env["PYTEST_ADDOPTS"] = "-p no:cacheprovider --basetemp=.pytest-tmp"
    os.makedirs(".pytest-tmp", exist_ok=True)
    
    print("==================================================")
    print(f"RUNNING COGNIMESH MASTER VERIFICATION SUITE")
    print(f"Total validation scripts to execute: {len(scripts)}")
    print("==================================================")
    
    success_count = 0
    failure_count = 0
    
    for script in scripts:
        script_path = os.path.join(script_dir, script)
        print(f"\n[{success_count + failure_count + 1}/{len(scripts)}] Executing {script}...")
        
        res = subprocess.run([sys.executable, script_path], capture_output=True, text=True, env=env)
        
        if res.returncode == 0:
            print(f"[PASS] {script}")
            success_count += 1
        else:
            print(f"[FAIL] {script} (Exit Code {res.returncode})")
            print("--- Output ---")
            print(res.stdout)
            print("--- Error ---")
            print(res.stderr)
            print("--------------")
            failure_count += 1
            break # Stop on first failure to debug
            
    print("\n==================================================")
    print("MASTER VERIFICATION SUMMARY")
    print("==================================================")
    print(f"Total Suites: {len(scripts)}")
    print(f"Passed:       {success_count}")
    print(f"Failed:       {failure_count}")
    
    if failure_count == 0:
        print("\n[SUCCESS] ALL PROJECT MODULES AND E2E SCENARIOS FULLY VERIFIED!")
        sys.exit(0)
    else:
        print("\n[ERROR] VERIFICATION FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
