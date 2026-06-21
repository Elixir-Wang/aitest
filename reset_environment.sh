#!/bin/bash
# 一键重置探索任务环境

echo "========================================"
echo "探索任务环境重置脚本"
echo "========================================"
echo ""

# 1. 重置卡住的任务
echo "【步骤 1】重置卡住的任务..."
sqlite3 apps/backend/data/ai_testing.db "UPDATE exploration_runs SET status='blocked', result_summary='任务已重置，请重启后端服务后重新启动', finished_at=datetime('now') WHERE status='running';"

# 检查结果
count=$(sqlite3 apps/backend/data/ai_testing.db "SELECT COUNT(*) FROM exploration_runs WHERE status='running';")
if [ "$count" = "0" ]; then
    echo "✓ 已重置所有 running 状态的任务"
else
    echo "✗ 仍有 $count 个 running 任务"
fi

echo ""

# 2. 显示最近的任务
echo "【步骤 2】最近的任务状态..."
sqlite3 -header -column apps/backend/data/ai_testing.db "SELECT id, status, substr(result_summary, 1, 40) as summary FROM exploration_runs ORDER BY created_at DESC LIMIT 3;"

echo ""

# 3. 检查代码修复
echo "【步骤 3】验证代码修复..."
cd /Users/wanghongbao/project/test_project
python3 << 'EOF'
with open('apps/backend/app/services/exploration/unified_orchestrator.py', 'r') as f:
    content = f.read()
    checks = {
        'execution_starting': '早期事件发布',
        'except Exception as error:': '异常捕获',
    }
    all_ok = True
    for key, desc in checks.items():
        if key in content:
            print(f"  ✓ {desc}")
        else:
            print(f"  ✗ {desc}")
            all_ok = False
    if all_ok:
        print("\n✓ 代码修复已就位")
    else:
        print("\n✗ 代码修复不完整")
EOF

echo ""
echo "========================================"
echo "重置完成"
echo "========================================"
echo ""
echo "⚠️  重要: 现在必须重启后端服务！"
echo ""
echo "请执行以下操作:"
echo ""
echo "1. 找到后端进程:"
echo "   ps aux | grep uvicorn"
echo ""
echo "2. 停止后端服务:"
echo "   kill -9 <进程ID>"
echo ""
echo "3. 重启后端服务:"
echo "   cd apps/backend"
echo "   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "4. 在前端创建新的探索任务（不是重启旧任务）"
echo ""
echo "5. 观察前端是否收到事件流"
echo ""
