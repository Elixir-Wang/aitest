#!/usr/bin/env python3
import shutil, os

src = "/pytest_requests"
dst = "/Users/wanghongbao/project/test_project/apps/backend/data/projects/project-75fec50973f2adf6/api_automation/pytest_requests"

os.makedirs(dst, exist_ok=True)

for item in os.listdir(src):
    s = os.path.join(src, item)
    d = os.path.join(dst, item)
    if os.path.isdir(s):
        if os.path.exists(d):
            shutil.rmtree(d)
        shutil.copytree(s, d)
    else:
        shutil.copy2(s, d)

# Verify
print("=== Target directory contents ===")
for root, dirs, files in os.walk(dst):
    level = root.replace(dst, '').count(os.sep)
    indent = ' ' * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = ' ' * 2 * (level + 1)
    for f in files:
        print(f"{subindent}{f}")
