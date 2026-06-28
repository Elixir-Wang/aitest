#!/bin/bash

echo "=========================================="
echo "登录态和探索速度诊断工具"
echo "=========================================="

cd /Users/wanghongbao/project/test_project/apps/backend

ENV_ID="env-c3bc1023763dbb16"

echo ""
echo "【1. 检查登录态状态】"
.venv/bin/python3 -c "
import sys
sys.path.insert(0, '.')
from app.core.environment_auth_state import auth_state_summary

summary = auth_state_summary('$ENV_ID', 'account_password', True)
print(f'  登录态状态: {summary[\"status\"]}')
print(f'  是否需要重新登录: {summary[\"status\"] != \"valid\"}')"

echo ""
echo "【2. 最近的自动登录事件】"
if [ -f "data/projects/environments/$ENV_ID/auth/auto-login-events.jsonl" ]; then
    echo "  最后5条事件:"
    tail -5 "data/projects/environments/$ENV_ID/auth/auto-login-events.jsonl" | while read line; do
        echo "    $(echo $line | jq -r '.kind + \" - \" + .recorded_at')"
    done
else
    echo "  无登录事件记录"
fi

echo ""
echo "【3. 当前自动登录状态】"
if [ -f "data/projects/environments/$ENV_ID/auth/auto-login-status.json" ]; then
    .venv/bin/python3 -c "
import json
with open('data/projects/environments/$ENV_ID/auth/auto-login-status.json') as f:
    status = json.load(f)
print(f'  状态: {status.get(\"status\")}')
print(f'  消息: {status.get(\"message\")}')
print(f'  更新时间: {status.get(\"updated_at\")}')"
else
    echo "  状态文件不存在"
fi

echo ""
echo "【4. 后端进程状态】"
if pgrep -f "uvicorn.*main:app" > /dev/null; then
    echo "  ✅ 后端正在运行"
else
    echo "  ❌ 后端未运行"
fi

echo ""
echo "【5. Playwright进程】"
if pgrep -f "node.*ai-letter-login" > /dev/null; then
    echo "  ⚠️  有Playwright登录进程在运行"
    pgrep -f "node.*ai-letter-login"
else
    echo "  ✅ 无Playwright登录进程"
fi

echo ""
echo "=========================================="
echo "建议："
echo "  如果登录态有效，应该不需要重新登录"
echo "  如果显示'登录中'，可能是前端显示问题"
echo "  查看前端Network看调用了什么接口"
echo "=========================================="
