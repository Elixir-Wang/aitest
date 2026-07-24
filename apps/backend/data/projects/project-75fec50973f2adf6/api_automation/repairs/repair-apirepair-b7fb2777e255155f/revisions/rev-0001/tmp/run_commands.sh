#!/bin/bash
echo "=== 1. python3 --version ==="
python3 --version 2>&1
echo ""
echo "=== 2. which python3 ==="
which python3 2>&1
echo ""
echo "=== 3. ls -la /pytest_requests/ ==="
ls -la /pytest_requests/ 2>&1
echo ""
echo "=== 4. ls -la /pytest_requests/testcases/openapi/v1/agent/analysis/post/ ==="
ls -la /pytest_requests/testcases/openapi/v1/agent/analysis/post/ 2>&1
echo ""
echo "=== 5. cat /pytest_requests/testcases/openapi/v1/agent/analysis/post/test_api.py | head -5 ==="
head -5 /pytest_requests/testcases/openapi/v1/agent/analysis/post/test_api.py 2>&1
