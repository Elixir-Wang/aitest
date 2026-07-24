"""
观察证据记录工具。

跨进程安全地记录脱敏后的实际响应，供 AI 修复流程校准测试数据/Oracle。
使用文件锁实现互斥：Windows 用 msvcrt，POSIX 用 fcntl。
"""
import json
import os
import sys
import tempfile
import shutil


def _sanitize_headers(headers: dict) -> dict:
    """移除敏感请求头字段"""
    sensitive_keys = {
        "authorization", "cookie", "set-cookie", "x-api-key", "api-key",
        "cybertron-robot-key", "cybertron-robot-token",
    }
    return {k: v for k, v in headers.items() if k.lower() not in sensitive_keys}


def _sanitize_body(obj):
    """递归脱敏包含敏感字段名的值"""
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            kl = k.lower()
            if any(s in kl for s in ("token", "password", "secret", "cookie",
                                      "authorization", "api_key", "apikey")):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = _sanitize_body(v)
        return sanitized
    elif isinstance(obj, list):
        return [_sanitize_body(item) for item in obj]
    return obj


def _acquire_lock(f, lock_path: str):
    """获取文件锁"""
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)


def _release_lock(f, lock_path: str):
    """释放文件锁"""
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def record_observation(case: dict, response) -> None:
    """
    记录脱敏后的实际响应到观察文件。

    case: 测试用例 dict，必须包含 id 和 test_point_key
    response: requests.Response 对象

    观察文件路径由环境变量 API_OBSERVATION_RESULT_PATH 指定。
    未设置该环境变量时静默跳过。
    """
    obs_path = os.environ.get("API_OBSERVATION_RESULT_PATH")
    if not obs_path:
        return

    case_id = case.get("id") or case.get("case_id", "")
    test_point_key = case.get("test_point_key", "")

    # 构建观察记录
    resp_headers = _sanitize_headers(dict(response.headers))

    # 尝试解析 JSON body
    try:
        resp_body = response.json()
        resp_body = _sanitize_body(resp_body)
    except (json.JSONDecodeError, ValueError):
        content_type = response.headers.get("Content-Type", "")
        resp_body = {
            "_type": content_type,
            "_size": len(response.content),
            "_summary": str(response.content[:500]),
        }

    observation = {
        "case_id": case_id,
        "test_point_key": test_point_key,
        "status_code": response.status_code,
        "response_headers": resp_headers,
        "response_body": resp_body,
    }

    # 使用文件锁安全写入
    lock_path = obs_path + ".lock"
    with open(lock_path, "w") as lock_f:
        _acquire_lock(lock_f, lock_path)
        try:
            # 读取已有记录
            existing = []
            if os.path.exists(obs_path):
                with open(obs_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                existing.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass

            # 追加或更新
            updated = False
            for i, rec in enumerate(existing):
                if rec.get("case_id") == case_id and rec.get("test_point_key") == test_point_key:
                    existing[i] = observation
                    updated = True
                    break
            if not updated:
                existing.append(observation)

            # 原子写入
            tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(obs_path))
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_f:
                for rec in existing:
                    tmp_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            shutil.move(tmp_path, obs_path)
        finally:
            _release_lock(lock_f, lock_path)