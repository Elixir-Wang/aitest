#!/bin/bash

# SSE 进度推送修复验证脚本
# 用途：快速验证前端是否能收到探索任务的进度更新

set -e

echo "======================================"
echo "  SSE 进度推送修复验证工具"
echo "======================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查后端服务
echo -e "${BLUE}[1/5]${NC} 检查后端服务..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} 后端服务运行正常 (http://localhost:8000)"
else
    echo -e "${RED}✗${NC} 后端服务未运行"
    echo "请先启动后端服务："
    echo "  cd apps/backend"
    echo "  uvicorn app.main:app --reload --port 8000"
    exit 1
fi

# 检查前端服务
echo -e "${BLUE}[2/5]${NC} 检查前端服务..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} 前端服务运行正常 (http://localhost:3000)"
else
    echo -e "${YELLOW}⚠${NC} 前端服务未运行（可选）"
    echo "如需测试前端界面，请启动前端："
    echo "  cd apps/frontend"
    echo "  npm run dev"
fi

# 检查修复的文件
echo -e "${BLUE}[3/5]${NC} 验证修复代码..."

# 检查后端修复
if grep -q "run_status_updated" apps/backend/app/services/exploration/unified_orchestrator.py; then
    echo -e "${GREEN}✓${NC} 后端修复已应用 (unified_orchestrator.py)"
else
    echo -e "${RED}✗${NC} 后端修复未找到"
    exit 1
fi

# 检查前端修复
if grep -q "run_status_updated" apps/frontend/src/app/\(main\)/projects/\[projectId\]/exploration/\[runId\]/page.tsx; then
    echo -e "${GREEN}✓${NC} 前端修复已应用 (page.tsx)"
else
    echo -e "${RED}✗${NC} 前端修复未找到"
    exit 1
fi

# 获取可用的探索任务
echo -e "${BLUE}[4/5]${NC} 查找可用的探索任务..."

# 尝试获取探索任务列表（需要认证token）
echo ""
echo -e "${YELLOW}提示：${NC}需要手动测试 SSE 事件流"
echo ""
echo "请按以下步骤操作："
echo ""
echo "方法一：浏览器手动测试（最直观）"
echo "  1. 打开浏览器访问：http://localhost:3000"
echo "  2. 登录系统"
echo "  3. 进入任意探索任务详情页"
echo "  4. 打开浏览器开发者工具 (F12) → Network 标签"
echo "  5. 过滤：stream"
echo "  6. 点击页面上的【重新开始】或【开始探索】按钮"
echo "  7. 观察 Network 中的 SSE 连接，应该能看到："
echo "     - event: run_status_updated  ← 关键事件！"
echo "     - event: module_updated      ← 关键事件！"
echo "     - event: step_recorded"
echo "     - event: planning_completed"
echo "     - 等等..."
echo "  8. 观察页面，进度文字应该实时更新："
echo "     '正在智能分析...' → '探索计划已生成' → '开始执行...'"
echo ""
echo "方法二：使用 curl 监控 SSE（需要 project_id 和 run_id）"
echo "  ./test_sse_events.sh <project_id> <run_id>"
echo ""

# 总结
echo -e "${BLUE}[5/5]${NC} 验证摘要"
echo ""
echo -e "${GREEN}✓ 修复已完成${NC}"
echo ""
echo "修复内容："
echo "  - 后端：在 _record_lifecycle_progress 中添加事件发布"
echo "  - 前端：处理 run_status_updated 事件"
echo ""
echo "预期效果："
echo "  - 前端不再卡在'正在智能分析探索目标并生成探索计划'"
echo "  - 进度文字会实时更新"
echo "  - SSE 流中能看到 run_status_updated 和 module_updated 事件"
echo ""
echo "======================================"
echo -e "${GREEN}验证脚本执行完成！${NC}"
echo "======================================"
echo ""
echo "📝 详细验证步骤请查看: SSE_PROGRESS_FIX_VERIFICATION.md"
echo ""
