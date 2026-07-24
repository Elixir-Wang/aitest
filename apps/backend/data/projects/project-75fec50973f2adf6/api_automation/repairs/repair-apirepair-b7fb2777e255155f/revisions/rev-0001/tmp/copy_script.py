import shutil, os

src = "/pytest_requests"
dst = "/Users/wanghongbao/project/test_project/apps/backend/data/projects/project-75fec50973f2adf6/api_automation/pytest_requests"

for item in os.listdir(src):
    s = os.path.join(src, item)
    d = os.path.join(dst, item)
    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copy2(s, d)
print("Copy complete")
