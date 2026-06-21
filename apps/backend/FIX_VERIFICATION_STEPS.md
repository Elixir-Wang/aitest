# 探索任务修复验证步骤 ✅

## 🎯 快速验证（3步）

### 步骤1：重启后端服务
```bash
cd apps/backend

# 方式1：使用 uvicorn
pkill -f uvicorn
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方式2：如果有启动脚本
./start.sh  # 或你的启动脚本
```

### 步骤2：创建测试任务
在前端界面操作：
1. 进入项目 → 探索任务
2. 点击"新建探索任务"
3. 填写配置：
   - **项目**: 选择任意项目
   - **环境**: 选择已配置的环境
   - **目标URL**: 输入要探索的网站
   - **探索范围**: 例如 "全部站点" 或具体页面
4. 点击"保存" → "开始探索"

### 步骤3：观察结果
**预期行为**：
- ✅ 任务状态: `pending` → `queued` → `running` → `completed/partial`
- ✅ 日志输出: 无 `'sqlite3.Row' object has no attribute 'get'` 错误
- ✅ 产物生成: 探索报告、页面信息等

**如果失败**：
```bash
# 查看错误日志
tail -50 logs/app/$(date +%Y-%m-%d).log

# 查看任务状态
sqlite3 data/ai_testing.db "
SELECT id, status, result_summary 
FROM exploration_runs 
ORDER BY created_at DESC LIMIT 1;"
```

---

## 📊 详细验证

### 检查修复是否生效
```bash
# 查看代码修改
git diff app/repositories/exploration_repo.py

# 应该看到3处修改：
# - find_by_id() 转换为 dict
# - list_by_project() 转换为 dict 列表
# - list_visible() 转换为 dict 列表
```

### 查看实时日志
```bash
# 开启日志监控（新终端窗口）
tail -f logs/app/$(date +%Y-%m-%d).log | grep -E "exploration|ERROR|Exception"
```

### 检查Playwright
```bash
cd runners/playwright

# 检查 Playwright 版本
npx playwright --version

# 如果需要安装浏览器
npx playwright install chromium
```

---

## ⚠️ 常见问题

### 问题1：后端服务启动失败
```bash
# 检查端口占用
lsof -i :8000

# 杀死占用进程
kill -9 <PID>
```

### 问题2：Playwright 未安装
```bash
cd runners/playwright
npm install
npx playwright install
```

### 问题3：数据库锁定
```bash
# 检查数据库连接
lsof data/ai_testing.db

# 如果有问题，重启服务
```

---

## ✨ 成功标志

看到以下内容说明修复成功：

1. **后端日志**（无错误）：
```
INFO | 站点探索开始执行
INFO | Playwright 探索脚本执行成功
INFO | 探索完成，状态 completed
```

2. **任务状态**（completed 或 partial）：
```bash
sqlite3 data/ai_testing.db "
SELECT status FROM exploration_runs 
ORDER BY created_at DESC LIMIT 1;"
# 输出: completed 或 partial（不是 blocked）
```

3. **前端显示**：
   - 任务列表显示绿色完成状态
   - 可以查看探索报告
   - 有页面和元素数据

---

## 📞 需要帮助？

如果验证失败，请提供：
1. 错误日志（最后100行）
2. 任务状态和错误信息
3. 浏览器控制台错误（如果有）

```bash
# 收集诊断信息
tail -100 logs/app/$(date +%Y-%m-%d).log > diagnosis.log
sqlite3 data/ai_testing.db "SELECT * FROM exploration_runs ORDER BY created_at DESC LIMIT 1;" >> diagnosis.log
```
