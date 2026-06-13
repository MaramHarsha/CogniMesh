#!/usr/bin/env python3
"""
Validation script for Module 14: Object Explorer, Object Views, And Analytics
Checks that the frontend React app is set up correctly in apps/console.
"""

import sys
from pathlib import Path

def print_status(msg: str, success: bool):
    """Print a colored status message."""
    if success:
        print(f"\033[92m[PASS]\033[0m {msg}")
    else:
        print(f"\033[91m[FAIL]\033[0m {msg}")

def check_file_exists(file_path: Path) -> bool:
    """Check if a file exists."""
    exists = file_path.is_file()
    print_status(f"File exists: {file_path.name}", exists)
    return exists

def run_checks():
    print("Running Module 14 Validation...")
    root_dir = Path(__file__).parent.parent
    console_dir = root_dir / "apps" / "console"
    
    success = True
    
    # Check directory structure
    if not console_dir.is_dir():
        print_status(f"Directory exists: apps/console", False)
        return False
    print_status(f"Directory exists: apps/console", True)
    
    # Check key files
    files_to_check = [
        "package.json",
        "index.html",
        "vite.config.ts",
        "Dockerfile",
        "src/App.tsx",
        "src/index.css",
        "src/components/Layout.tsx",
        "src/components/ObjectBrowser.tsx",
        "src/components/ObjectExplorer.tsx",
        "src/components/ObjectView.tsx"
    ]
    
    for filename in files_to_check:
        if not check_file_exists(console_dir / filename):
            success = False
            
    # Check docker-compose.yml
    compose_file = root_dir / "infra" / "compose" / "docker-compose.yml"
    if compose_file.is_file():
        content = compose_file.read_text()
        has_console = "console:" in content and "context: ../../apps/console" in content
        print_status("docker-compose.yml includes console service", has_console)
        if not has_console:
            success = False
    else:
        print_status("docker-compose.yml exists", False)
        success = False

    return success

if __name__ == "__main__":
    if run_checks():
        print("\nModule 14 validation passed!")
        sys.exit(0)
    else:
        print("\nModule 14 validation failed.")
        sys.exit(1)
