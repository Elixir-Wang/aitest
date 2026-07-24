"""Quick verification script"""
import sys
sys.path.insert(0, '/Users/wanghongbao/project/test_project/apps/backend/data/projects/project-75fec50973f2adf6/api_automation/pytest_requests')

from utils.data_loader import load_cases
from utils.assertions import execute_assertions, assert_status_code, assert_jsonpath_equals, assert_jsonpath_type, assert_jsonpath_exists
from utils.assert_utils import jsonpath_extract, jsonpath_exists
from utils.observations import record_observation
print("All imports successful")

cases = load_cases('/Users/wanghongbao/project/test_project/apps/backend/data/projects/project-75fec50973f2adf6/api_automation/pytest_requests/testcases/openapi/v1/agent/analysis/post/cases.yaml')
print(f"Loaded {len(cases)} cases")
for c in cases:
    print(f"  - {c.get('id')}: {c.get('title')} (oracle: {c.get('oracle_status')})")
