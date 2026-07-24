import sys
sys.path.insert(0, '.')
from utils.data_loader import load_cases
from utils.assertions import execute_assertions, assert_status_code, assert_jsonpath_equals, assert_jsonpath_type, assert_jsonpath_exists
from utils.assert_utils import jsonpath_extract, jsonpath_exists
print('All imports successful')
# Test loading cases
cases = load_cases('testcases/openapi/v1/agent/analysis/post/cases.yaml')
print(f'Loaded {len(cases)} cases')
for c in cases:
    print(f'  - {c.get("id")}: {c.get("title")} (oracle: {c.get("oracle_status")})')
