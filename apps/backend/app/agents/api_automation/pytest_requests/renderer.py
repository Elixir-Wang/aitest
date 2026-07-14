import re

from app.agents.api_automation.pytest_requests.schemas import (
    GeneratedCodeFile,
    PytestRequestsGenerationInput,
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug or "generated"


def render_pytest_requests_files(input_data: PytestRequestsGenerationInput) -> list[GeneratedCodeFile]:
    endpoint = input_data.endpoint
    module = endpoint.module or _infer_module(endpoint.path)
    feature = endpoint.feature or _infer_feature(endpoint.path)

    files: list[GeneratedCodeFile] = []
    if input_data.is_first_time:
        files.extend(_generate_base_files())
    else:
        files.extend(_generate_repeat_files())
    files.extend(_generate_api_files(module, feature, endpoint))
    files.extend(_generate_testcase_files(module, feature, endpoint, input_data.cases))
    return files


def _infer_module(path: str) -> str:
    parts = path.strip("/").split("/")
    return parts[0].lower() if parts and parts[0] else "common"


def _infer_feature(path: str) -> str:
    parts = path.strip("/").split("/")
    return parts[1].lower() if len(parts) > 1 else "default"


def _file(key: str, language: str, content: str, kind: str = "") -> GeneratedCodeFile:
    return GeneratedCodeFile(key=key, language=language, content=content, kind=kind)


def client_py() -> str:
    return (
        '"""API 客户端 - 支持 multipart、path 模板与环境变量扩展"""\n'
        "from __future__ import annotations\n\n"
        "import os\nimport re\nfrom pathlib import Path\nfrom urllib.parse import quote\n\nimport requests\n\n\n"
        "_ENV_PATTERN = re.compile(r\"\\$\\{([A-Za-z_][A-Za-z0-9_]*)\\}\")\n"
        "_PATH_PATTERN = re.compile(r\"\\{([A-Za-z_][A-Za-z0-9_]*)\\}\")\n\n\n"
        "def _expand_environment(value):\n"
        "    if isinstance(value, dict):\n"
        "        return {key: _expand_environment(item) for key, item in value.items()}\n"
        "    if isinstance(value, list):\n"
        "        return [_expand_environment(item) for item in value]\n"
        "    if not isinstance(value, str):\n"
        "        return value\n"
        "    full_match = _ENV_PATTERN.fullmatch(value)\n"
        "    if full_match:\n"
        "        return os.environ.get(full_match.group(1), \"\")\n"
        "    return _ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), \"\"), value)\n\n\n"
        "def _expand_path(path: str, test_data: dict | None) -> str:\n"
        "    values = {\n"
        "        key: item.get(\"value\") if isinstance(item, dict) and \"value\" in item else item\n"
        "        for key, item in (test_data or {}).items()\n"
        "    }\n"
        "    expanded = _expand_environment(path)\n"
        "    return _PATH_PATTERN.sub(\n"
        "        lambda match: quote(str(_expand_environment(values.get(match.group(1), match.group(0)))), safe=\"\"),\n"
        "        expanded,\n"
        "    )\n\n\n"
        "def _build_files(file_specs: dict):\n"
        "    files: list = []\n"
        "    handles: list = []\n"
        "    try:\n"
        "        for field_name, raw_specs in file_specs.items():\n"
        "            specs = raw_specs if isinstance(raw_specs, list) else [raw_specs]\n"
        "            for raw_spec in specs:\n"
        "                spec = raw_spec if isinstance(raw_spec, dict) else {\"path\": raw_spec}\n"
        "                file_path = Path(_expand_environment(spec.get(\"path\", \"\"))).expanduser()\n"
        "                if not str(file_path) or not file_path.is_file():\n"
        "                    raise RuntimeError(f\"Upload file does not exist for field {field_name}: {file_path}\")\n"
        "                handle = file_path.open(\"rb\")\n"
        "                handles.append(handle)\n"
        "                filename = _expand_environment(spec.get(\"filename\")) or file_path.name\n"
        "                content_type = _expand_environment(spec.get(\"content_type\")) or \"application/octet-stream\"\n"
        "                files.append((field_name, (filename, handle, content_type)))\n"
        "        return files, handles\n"
        "    except Exception:\n"
        "        for handle in handles:\n"
        "            handle.close()\n"
        "        raise\n\n\n"
        "class ApiClient:\n"
        "    def __init__(self, base_url: str = \"\", timeout: int = 30):\n"
        "        self.base_url = base_url.rstrip(\"/\")\n"
        "        self.timeout = timeout\n"
        "        self.session = requests.Session()\n"
        "        bearer = os.environ.get(\"API_AUTH_BEARER\", \"\")\n"
        "        if bearer:\n"
        "            self.session.headers[\"Authorization\"] = f\"Bearer {bearer}\"\n\n"
        "    def request(self, request_data: dict, test_data: dict | None = None):\n"
        "        method = request_data.get(\"method\", \"GET\")\n"
        "        path = _expand_path(request_data.get(\"path\", \"\"), test_data or {})\n"
        "        url = f\"{self.base_url}{path}\"\n"
        "        query = _expand_environment(request_data.get(\"query\") or {})\n"
        "        headers = _expand_environment(request_data.get(\"headers\") or {})\n"
        "        body = _expand_environment(request_data.get(\"body\")) if \"body\" in request_data else None\n"
        "        files, handles = _build_files(request_data.get(\"files\") or {})\n"
        "        try:\n"
        "            return self.session.request(\n"
        "                method,\n"
        "                url,\n"
        "                params=query or None,\n"
        "                data=body if files else None,\n"
        "                json=None if files else body,\n"
        "                files=files or None,\n"
        "                headers=headers or None,\n"
        "                timeout=self.timeout,\n"
        "            )\n"
        "        finally:\n"
        "            for handle in handles:\n"
        "                handle.close()\n"
    )


def assertions_py() -> str:
    return (
        '"""断言工具 - 支持 status_code、jsonpath、jsonpath_type、schema、response_time、body_sha256 等"""\n'
        "from __future__ import annotations\n\n"
        "import hashlib\nimport json\nimport re\n\n"
        "_JSONPATH_PATTERN = re.compile(r\"\\$\\.[^.]+(?:\\.[^.]+)*\")\n\n\n"
        "def get_nested(data, path: str):\n"
        "    for key in path.split(\".\"):\n"
        "        if isinstance(data, dict):\n"
        "            data = data.get(key)\n"
        "        else:\n"
        "            return None\n"
        "    return data\n\n\n"
        "def _resolve_jsonpath(response, jsonpath: str):\n"
        "    body = response.json() if hasattr(response, \"json\") and callable(response.json) else response.json()\n"
        "    match = _JSONPATH_PATTERN.fullmatch(jsonpath)\n"
        "    if not match:\n"
        "        return None\n"
        "    cursor = body\n"
        "    for key in [segment for segment in match.group(0)[2:].split(\".\") if segment]:\n"
        "        if isinstance(cursor, dict):\n"
        "            cursor = cursor.get(key)\n"
        "        else:\n"
        "            return None\n"
        "    return cursor\n\n\n"
        "def _validate_jsonpath_type(value, expected: str) -> bool:\n"
        "    mapping = {\n"
        "        \"string\": str,\n"
        "        \"number\": (int, float),\n"
        "        \"integer\": int,\n"
        "        \"boolean\": bool,\n"
        "        \"array\": list,\n"
        "        \"object\": dict,\n"
        "        \"null\": type(None),\n"
        "    }\n"
        "    target = mapping.get(expected)\n"
        "    if target is None:\n"
        "        return False\n"
        "    return isinstance(value, target)\n\n\n"
        "def _validate_schema(value, schema: dict) -> bool:\n"
        "    expected_type = schema.get(\"type\")\n"
        "    type_map = {\"object\": dict, \"array\": list, \"string\": str, \"number\": (int, float), \"integer\": int, \"boolean\": bool}\n"
        "    if expected_type and not isinstance(value, type_map.get(expected_type, object)):\n"
        "        return False\n"
        "    if expected_type == \"object\":\n"
        "        for required in schema.get(\"required\", []):\n"
        "            if required not in value:\n"
        "                return False\n"
        "        for key, sub_schema in (schema.get(\"properties\") or {}).items():\n"
        "            if key in value and not _validate_schema(value[key], sub_schema):\n"
        "                return False\n"
        "    elif expected_type == \"array\":\n"
        "        item_schema = schema.get(\"items\")\n"
        "        if item_schema:\n"
        "            for item in value:\n"
        "                if not _validate_schema(item, item_schema):\n"
        "                    return False\n"
        "    return True\n\n\n"
        "def assert_response_assertions(response, assertions: list) -> None:\n"
        "    for assertion in assertions:\n"
        "        atype = assertion.get(\"type\")\n"
        "        if atype == \"status_code\":\n"
        "            assert response.status_code == assertion[\"expected\"]\n"
        "        elif atype == \"content_type\":\n"
        "            assert assertion[\"expected\"] in response.headers.get(\"Content-Type\", \"\")\n"
        "        elif atype == \"header_exists\":\n"
        "            assert assertion[\"path\"] in response.headers\n"
        "        elif atype == \"body_not_empty\":\n"
        "            assert bool(response.content)\n"
        "        elif atype == \"body_sha256\":\n"
        "            assert hashlib.sha256(response.content).hexdigest() == assertion[\"expected\"]\n"
        "        elif atype == \"jsonpath\":\n"
        "            value = _resolve_jsonpath(response, assertion[\"path\"])\n"
        "            assert value == assertion[\"expected\"]\n"
        "        elif atype == \"jsonpath_type\":\n"
        "            value = _resolve_jsonpath(response, assertion[\"path\"])\n"
        "            assert _validate_jsonpath_type(value, assertion[\"expected\"]) is True\n"
        "        elif atype == \"response_time_max\":\n"
        "            assert response.elapsed.total_seconds() * 1000 <= assertion[\"expected\"]\n"
        "        elif atype == \"schema_basic\":\n"
        "            body = response.json()\n"
        "            assert _validate_schema(body, assertion[\"expected\"]) is True\n"
        "        elif atype == \"body\":\n"
        "            body = response.json()\n"
        "            for key, expected in assertion.get(\"expected\", {}).items():\n"
        "                assert get_nested(body, key) == expected\n"
    )


def _generate_repeat_files() -> list[GeneratedCodeFile]:
    """每次 generate 都重新生成的"项目级"固定文件，避免重复写各 endpoint 独有目录下的 __init__.py。"""
    return [
        _file("api/__init__.py", "python", ""),
        _file("api/client.py", "python", client_py()),
        _file("utils/assertions.py", "python", assertions_py()),
    ]


def _generate_base_files() -> list[GeneratedCodeFile]:
    return [
        _file(
            "pytest.ini",
            "ini",
            "[pytest]\ntestpaths = testcases\npython_files = test_*.py\naddopts = -v --tb=short --import-mode=importlib\npythonpath = .\n",
        ),
        _file(
            "pyproject.toml",
            "toml",
            '[project]\nname = "pytest-requests-project"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n'
            'dependencies = ["pytest>=8.0.0", "requests>=2.31.0", "pyyaml>=6.0.0"]\n',
        ),
        _file("requirements.txt", "text", "pytest>=8.0.0\nrequests>=2.31.0\npyyaml>=6.0.0\n"),
        _file(
            "conftest.py",
            "python",
            '"""根级 fixture"""\nimport os\nimport pytest\nfrom api.client import ApiClient\n\n\n'
            '@pytest.fixture(scope="session")\ndef api_client():\n'
            '    base_url = os.environ.get("API_BASE_URL", "")\n'
            '    if not base_url:\n'
            '        pytest.skip("API_BASE_URL not configured")\n'
            '    return ApiClient(base_url=base_url)\n',
        ),
        _file("utils/__init__.py", "python", ""),
        _file(
            "utils/data_loader.py",
            "python",
            '"""数据加载工具"""\nimport yaml\nfrom pathlib import Path\n\n\n'
            "def load_yaml(test_file: str, filename: str):\n"
            '    path = Path(test_file).parent / filename\n'
            '    with open(path, "r", encoding="utf-8") as f:\n'
            "        return yaml.safe_load(f)\n\n\n"
            "def load_cases(test_file: str, filename: str):\n"
            "    return load_yaml(test_file, filename).get(\"cases\", [])\n",
        ),
        _file(
            "utils/assert_utils.py",
            "python",
            '"""断言工具。"""\nfrom utils.assertions import assert_response_assertions\n\n\n'
            "def assert_response(response, assertions):\n"
            "    if isinstance(assertions, dict):\n"
            "        legacy = []\n"
            "        if \"status_code\" in assertions:\n"
            "            legacy.append({\"type\": \"status_code\", \"expected\": assertions[\"status_code\"]})\n"
            "        for key, value in (assertions.get(\"body\") or {}).items():\n"
            "            legacy.append({\"type\": \"body\", \"path\": key, \"expected\": value})\n"
            "        if \"body_not_empty\" in assertions:\n"
            "            legacy.append({\"type\": \"body_not_empty\"})\n"
            "        return assert_response_assertions(response, legacy)\n"
            "    assert_response_assertions(response, assertions or [])\n",
        ),
        _file("utils/assertions.py", "python", assertions_py()),
        _file(
            "config/__init__.py",
            "python",
            "",
        ),
        _file(
            "config/settings.py",
            "python",
            '"""环境配置"""\nimport os\n\nAPI_BASE_URL = os.environ.get("API_BASE_URL", "")\n'
            'API_TIMEOUT = int(os.environ.get("API_TIMEOUT", "30"))\n'
            'API_AUTH_BEARER = os.environ.get("API_AUTH_BEARER", "")\n',
        ),
        _file("data/__init__.py", "python", ""),
        _file(
            "data/constants.py",
            "python",
            '"""公共常量"""\nclass HttpStatus:\n    OK = 200\n    CREATED = 201\n    BAD_REQUEST = 400\n    UNAUTHORIZED = 401\n    NOT_FOUND = 404\n    INTERNAL_ERROR = 500\n',
        ),
        _file(
            "data/common_users.yaml",
            "yaml",
            '# 公共测试用户\nusers:\n  test_user:\n    username: "test_user"\n    password: "Test@123456"\n'
            '  admin:\n    username: "admin"\n    password: "Admin@123456"\n',
        ),
        _file("fixtures/__init__.py", "python", ""),
    ]


def _generate_api_files(module: str, feature: str, endpoint) -> list[GeneratedCodeFile]:
    method = endpoint.method.upper()
    path = endpoint.path
    module_class = f"{module.title().replace('_', '')}API"
    return [
        _file("api/__init__.py", "python", ""),
        _file("api/client.py", "python", client_py()),
        _file(
            f"api/module_{module}.py",
            "python",
            f'"""API 模块 - {module}"""\nfrom api.client import ApiClient, get_client\n\n\n'
            f"class {module_class}:\n"
            f"    def __init__(self, client: ApiClient = None):\n"
            "        self._client = client\n\n"
            "    @property\n    def api(self):\n        return self._client or get_client()\n\n"
            f'    def {method.lower()}_{feature}(self, request_data=None, test_data=None, **kwargs):\n'
            f'        """{endpoint.summary or f"{method} {path}"}"""\n'
            f"        return self.api.request(\n"
            f"            {{\"method\": \"{method}\", \"path\": \"{path}\", **(request_data or {{}}), **kwargs}},\n"
            "            test_data,\n"
            "        )\n",
        ),
    ]


def _generate_testcase_files(module: str, feature: str, endpoint, cases: list) -> list[GeneratedCodeFile]:
    module_class = f"{module.title().replace('_', '')}API"
    test_file_key = f"testcases/{module}/{feature}/test_{feature}.py"
    data_file_key = f"testcases/{module}/{feature}/test_{feature}.yaml"
    return [
        _file("testcases/__init__.py", "python", "", kind="init"),
        _file("testcases/conftest.py", "python", "", kind="init"),
        _file(f"testcases/{module}/__init__.py", "python", "", kind="init"),
        _file(f"testcases/{module}/{feature}/__init__.py", "python", "", kind="init"),
        _file(
            test_file_key,
            "python",
            f'"""测试用例 - {module}/{feature}"""\nimport pytest\n'
            f"from api.module_{module} import {module_class}\n"
            f"from utils.data_loader import load_cases\n"
            f"from utils.assert_utils import assert_response\n\n\n"
            f'TEST_CASES = load_cases(__file__, "test_{feature}.yaml")\n\n\n'
            f"@pytest.mark.parametrize(\"case\", TEST_CASES)\n"
            f"def test_{feature}(case):\n"
            f"    api = {module_class}()\n"
            f"    request_data = case.get(\"request\", {{}})\n"
            f"    test_data = case.get(\"test_data\") or {{}}\n"
            f"    response = api.{endpoint.method.lower()}_{feature}(request_data=request_data, test_data=test_data)\n"
            f"    assert_response(response, case.get(\"assertions\", []))\n",
            kind="test",
        ),
        _file(data_file_key, "yaml", _cases_to_yaml(cases), kind="data"),
    ]


def _cases_to_yaml(cases: list) -> str:
    import yaml
    return yaml.dump({"cases": cases}, allow_unicode=True, default_flow_style=False)
