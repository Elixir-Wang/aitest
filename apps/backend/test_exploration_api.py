#!/usr/bin/env python3
"""
页面探索功能完整测试脚本
测试所有新增的API端点
"""

import requests
import json
import time

# 配置
BASE_URL = "http://localhost:8000/api/v1"
TEST_PROJECT_ID = "project-26ff9986b6318277"  # 从前端URL获取的项目ID
TEST_ENV_ID = "env-c3bc1023763dbb16"  # 从git status看到的环境ID

# 登录获取token
def login():
    """登录获取认证token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "admin", "password": "admin"}
    )
    if response.status_code == 200:
        result = response.json()
        # 响应包装在data字段中
        data = result.get("data", result)
        return data.get("access_token")
    else:
        print(f"登录失败: {response.status_code} {response.text}")
        return None

def get_headers(token):
    """构建请求头"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def test_create_exploration(token):
    """测试创建探索任务"""
    print("\n=== 测试1: 创建探索任务 ===")

    response = requests.post(
        f"{BASE_URL}/page-exploration/runs",
        headers=get_headers(token),
        json={
            "project_id": TEST_PROJECT_ID,
            "environment_id": TEST_ENV_ID,
            "title": "API测试探索任务",
            "scope": "http://localhost:3000",
            "goal": "测试页面探索功能是否正常工作",
            "forbidden_paths": "删除\n退出登录",
            "max_pages": 10,
            "max_actions": 100,
            "timeout_minutes": 30,
            "notes": "这是通过API测试脚本创建的"
        }
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        data = result.get('data', result)
        print(f"创建成功! Run ID: {data.get('id')}")
        print(f"状态: {data.get('status')}")
        return data.get('id')
    else:
        print(f"创建失败: {response.text}")
        return None

def test_get_exploration(token, run_id):
    """测试获取探索任务详情"""
    print(f"\n=== 测试2: 获取探索任务详情 ===")

    response = requests.get(
        f"{BASE_URL}/page-exploration/runs/{run_id}",
        headers=get_headers(token)
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        data = result.get('data', result)
        print(f"获取成功!")
        print(f"  - artifact_schema_version: {data.get('artifact_schema_version')}")
        print(f"  - unsupported_artifact: {data.get('unsupported_artifact')}")
        print(f"  - modules数量: {len(data.get('modules', []))}")
        if data.get('modules'):
            module = data['modules'][0]
            print(f"  - 模块名称: {module.get('module_name')}")
            print(f"  - 页面数量: {len(module.get('pages', []))}")
        return True
    else:
        print(f"获取失败: {response.text}")
        return False

def test_update_exploration(token, run_id):
    """测试更新探索任务"""
    print(f"\n=== 测试3: 更新探索任务 ===")

    response = requests.patch(
        f"{BASE_URL}/page-exploration/runs/{run_id}",
        headers=get_headers(token),
        json={
            "title": "API测试探索任务（已更新）",
            "notes": "通过PATCH端点更新了标题和备注",
            "max_pages": 20
        }
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        data = result.get('data', result)
        print(f"更新成功!")
        print(f"  - 新标题: {data.get('title')}")
        print(f"  - 新备注: {data.get('notes')}")
        print(f"  - max_pages: {data.get('max_pages')}")
        return True
    else:
        print(f"更新失败: {response.text}")
        return False

def test_start_exploration(token, run_id):
    """测试启动探索任务"""
    print(f"\n=== 测试4: 启动探索任务 ===")

    response = requests.post(
        f"{BASE_URL}/page-exploration/runs/{run_id}/start",
        headers=get_headers(token)
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        data = result.get('data', result)
        print(f"启动成功!")
        print(f"  - 状态: {data.get('status')}")
        print(f"  - 开始时间: {data.get('started_at')}")
        return True
    else:
        print(f"启动失败: {response.text}")
        return False

def test_stream_exploration(token, run_id):
    """测试SSE流"""
    print(f"\n=== 测试5: SSE实时流 ===")

    try:
        response = requests.get(
            f"{BASE_URL}/page-exploration/runs/{run_id}/stream",
            headers=get_headers(token),
            stream=True,
            timeout=10
        )

        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("SSE流连接成功，接收事件...")
            event_count = 0
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith('data:'):
                    event_count += 1
                    data = json.loads(line[5:].strip())
                    print(f"  事件 {event_count}: type={data.get('type')}, run_id={data.get('run_id')}")
                    if event_count >= 3:  # 只显示前3个事件
                        print("  ... (继续接收中)")
                        break
            return True
        else:
            print(f"连接失败: {response.text}")
            return False
    except Exception as e:
        print(f"SSE测试出错: {e}")
        return False

def test_stop_exploration(token, run_id):
    """测试停止探索任务"""
    print(f"\n=== 测试6: 停止探索任务 ===")

    # 等待一会儿再停止
    time.sleep(2)

    response = requests.post(
        f"{BASE_URL}/page-exploration/runs/{run_id}/stop",
        headers=get_headers(token)
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        data = result.get('data', result)
        print(f"停止成功!")
        print(f"  - 状态: {data.get('status')}")
        return True
    else:
        print(f"停止失败: {response.text}")
        return False

def test_get_report(token, run_id):
    """测试获取探索报告"""
    print(f"\n=== 测试7: 获取探索报告 ===")

    # 等待任务完成
    time.sleep(3)

    response = requests.get(
        f"{BASE_URL}/page-exploration/runs/{run_id}/artifacts",
        headers=get_headers(token)
    )

    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        data = result.get('data', result)
        print(f"获取报告成功!")
        print(f"  - 报告标题: {data.get('title')}")
        print(f"  - artifact_schema_version: {data.get('artifact_schema_version')}")
        print(f"  - 报告内容长度: {len(data.get('markdown_content', ''))}")
        print(f"  - 报告预览: {data.get('markdown_content', '')[:100]}...")
        return True
    else:
        print(f"获取报告失败: {response.text}")
        return False

def main():
    """主测试流程"""
    print("=" * 60)
    print("页面探索功能完整测试")
    print("=" * 60)

    # 登录
    print("\n>>> 正在登录...")
    token = login()
    if not token:
        print("❌ 登录失败，测试终止")
        return
    print(f"✅ 登录成功，获取到token")

    # 执行测试
    results = []

    # 1. 创建探索任务
    run_id = test_create_exploration(token)
    results.append(("创建探索任务", run_id is not None))
    if not run_id:
        print("\n❌ 无法创建探索任务，后续测试终止")
        return

    # 2. 获取探索任务详情
    success = test_get_exploration(token, run_id)
    results.append(("获取探索详情", success))

    # 3. 更新探索任务
    success = test_update_exploration(token, run_id)
    results.append(("更新探索任务", success))

    # 4. 启动探索任务
    success = test_start_exploration(token, run_id)
    results.append(("启动探索任务", success))

    # 5. 测试SSE流
    success = test_stream_exploration(token, run_id)
    results.append(("SSE实时流", success))

    # 6. 停止探索任务
    success = test_stop_exploration(token, run_id)
    results.append(("停止探索任务", success))

    # 7. 获取探索报告
    success = test_get_report(token, run_id)
    results.append(("获取探索报告", success))

    # 打印测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {test_name}")

    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！后端API完全正常工作！")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，需要检查")

if __name__ == "__main__":
    main()
