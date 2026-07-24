import shutil, os, subprocess

src = "/pytest_requests"
dst = "/Users/wanghongbao/project/test_project/apps/backend/data/projects/project-75fec50973f2adf6/api_automation/pytest_requests"

# Use rsync for reliable recursive copy including hidden files
result = subprocess.run(
    ["rsync", "-av", src + "/", dst + "/"],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Exit code:", result.returncode)
