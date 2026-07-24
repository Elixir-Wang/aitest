#!/usr/bin/env python3
import subprocess, os

src = "/pytest_requests"
dst = "/Users/wanghongbao/project/test_project/apps/backend/data/projects/project-75fec50973f2adf6/api_automation/pytest_requests"

# Ensure target exists
os.makedirs(dst, exist_ok=True)

# Use rsync to copy everything including hidden files
result = subprocess.run(
    ["rsync", "-av", "--delete", src + "/", dst + "/"],
    capture_output=True, text=True
)
print("=== RSYNC OUTPUT ===")
print(result.stdout)
if result.stderr:
    print("=== STDERR ===")
    print(result.stderr)
print("Exit code:", result.returncode)
