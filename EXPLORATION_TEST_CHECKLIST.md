# 探索功能执行测试清单

## 前置条件检查

### 1. 检查AI模型配置

```sql
-- 查询模型配置
SELECT * FROM model_assignments WHERE capability_id = 'site_exploration';
SELECT * FROM model_configs WHERE status = 'enabled';
```

**验证**：
- [ ] site_exploration 已分配模型
- [ ] 分配的模型状态为 enabled
- [ ] 模型配置有 api_key

### 2. 检查Playwright环境

```bash
# 检查playwright是否安装
which playwright

# 检查版本
playwright --version

# 检查chromium是否安装
playwright install chromium --dry-run
```

**验证**：
- [ ] playwright 命令可用
- [ ] chromium 浏览器已安装

### 3. 检查代码修改

```bash
# 检查 _execute_exploration 是否使用真实实现
grep -A 5 "def _execute_exploration" apps/backend/app/services/exploration/page_exploration_service.py
```

**验证**：
- [ ] 不再是 time.sleep(0.5) 的模拟实现
- [ ] 包含 resolve_model_selection
- [ ] 包含 create_page_exploration_agent

---

## 执行测试步骤

### 步骤1：配置AI模型（如果未配置）

1. 访问系统设置 → 模型配置
2. 点击"添加模型配置"
3. 填写配置：
   - 提供商：OpenAI
   - 模型：gpt-3.5-turbo（测试推荐）
   - Base URL：https://api.openai.com/v1
   - API Key：你的API密钥
4. 保存并启用
5. 进入"模型分配"
6. 为"站点探索智能体"分配刚创建的模型

### 步骤2：创建测试环境

1. 进入"探索" → "探索环境" Tab
2. 点击"新建环境"
3. 填写：
   - 环境名称：测试环境
   - 站点地址：https://example.com（测试用）
   - 登录策略：跳过登录
4. 保存

### 步骤3：创建探索任务

1. 进入"探索" → "探索列表" Tab
2. 点击"新建探索任务"
3. 填写：
   - 任务标题：测试探索
   - 选择项目：（选择任意项目）
   - 选择环境：测试环境
   - 探索目标：探索页面结构和链接
   - 探索范围：https://example.com
   - 最大页面数：5（测试建议小数量）
   - 最大操作数：100
   - 超时时间：30分钟
4. 保存

### 步骤4：启动探索

1. 在探索列表中找到刚创建的任务
2. 点击"开始探索"按钮
3. 观察任务中心通知

**预期行为**：
- ✅ 任务状态从"待执行"变为"运行中"
- ✅ 任务中心显示通知且不会立即消失
- ✅ 通知内容显示"探索进行中"

### 步骤5：查看实时进度

1. 点击探索任务进入详情页
2. 切换到"探索概览"Tab
3. 观察进度树

**预期行为**：
- ✅ 显示探索进度树（不是"暂无探索模块进度信息"）
- ✅ 可以看到模块→页面→步骤的层级结构
- ✅ 状态实时更新（待执行→运行中→已完成）

### 步骤6：查看探索日志

1. 在探索详情页切换到"探索计划"Tab
2. 观察实时日志

**预期行为**：
- ✅ 显示LLM调用日志
- ✅ 显示页面访问记录
- ✅ 显示元素提取信息

### 步骤7：等待探索完成

等待探索任务完成（5个页面约需3-5分钟）

**预期行为**：
- ✅ 任务状态最终变为"已完成"
- ✅ 显示结果摘要："探索完成，共探索 X 个页面"
- ✅ 任务中心显示完成通知

### 步骤8：查看探索产物

1. 返回探索首页
2. 切换到"探索产物"Tab
3. 查看产物列表

**预期行为**：
- ✅ 显示产物列表（不是"暂无探索产物"）
- ✅ 可以看到生成的产物文件
- ✅ 可以搜索和过滤产物

### 步骤9：查看产物文件

在服务器上检查实际生成的文件：

```bash
# 检查产物目录
PROJECT_ID="你的项目ID"
RUN_ID="你的探索任务ID"

# 查看run级产物
ls -la apps/backend/data/projects/$PROJECT_ID/page_exploration/runs/$RUN_ID/

# 应该包含：
# - discovered_pages.yaml
# - report.md
# - screenshots/ (如果有)
```

**预期文件**：
- ✅ `discovered_pages.yaml` - 发现的页面列表
- ✅ `report.md` - 探索报告
- ✅ 其他产物文件

---

## 问题排查

### 问题1：任务立即完成

**症状**：点击"开始探索"后，任务立即变为"已完成"，结果摘要显示"探索完成，共探索 0 个页面"

**原因**：代码修改未生效，仍在使用模拟实现

**排查**：
```bash
# 检查代码是否正确修改
grep -A 10 "def _execute_exploration" apps/backend/app/services/exploration/page_exploration_service.py | head -20
```

**解决**：
- 确认代码修改已保存
- 重启后端服务

### 问题2：报错"AI 能力未分配可用模型配置"

**症状**：任务状态变为"失败"，错误信息："AI 能力未分配可用模型配置，无法运行：站点探索智能体"

**原因**：未配置AI模型或未分配给site_exploration

**解决**：
1. 进入"设置" → "模型配置"
2. 添加模型配置（OpenAI/Azure等）
3. 进入"模型分配"
4. 为"站点探索智能体"分配模型

### 问题3：报错"模型配置未保存 API Key"

**症状**：任务失败，错误："模型配置未保存 API Key，无法用于 AI 能力运行"

**原因**：模型配置中API Key为空

**解决**：
1. 进入"设置" → "模型配置"
2. 编辑模型配置
3. 填写正确的API Key
4. 保存

### 问题4：报错"playwright command not found"

**症状**：任务失败，错误中包含"playwright: command not found"

**原因**：Playwright未安装

**解决**：
```bash
# 安装playwright
npm install -g playwright

# 安装浏览器
playwright install chromium
```

### 问题5：LLM调用失败

**症状**：任务失败，错误中包含"API key invalid"或"Rate limit exceeded"

**原因**：
- API Key无效
- API配额用完
- 网络连接问题

**解决**：
- 检查API Key是否正确
- 检查账户余额
- 检查网络连接（可能需要代理）

### 问题6：探索进度不显示

**症状**：探索详情页"探索概览"Tab显示"暂无探索模块进度信息"

**原因**：前端代码未修复或产物格式不对

**解决**：
- 确认前端代码已修复（之前的PR）
- 检查产物是否符合AgentPlan组件的格式要求

---

## 成本估算

### 测试成本（5个页面）

使用 GPT-3.5-turbo：
- 每页面：3-5次LLM调用
- 每次调用：约2K tokens输入 + 1K tokens输出
- 5个页面：约 (5 * 4 * 3K) = 60K tokens
- 成本：约 $0.05 - $0.10

使用 GPT-4：
- 成本：约 $0.50 - $1.00

### 生产环境成本（50个页面）

使用 GPT-3.5-turbo：
- 约 $0.25 - $0.50

使用 GPT-4：
- 约 $2.50 - $5.00

**建议**：
- 测试阶段使用 GPT-3.5-turbo
- 设置合理的 max_pages 限制（10-20页）
- 监控LLM调用次数

---

## 验收标准

### 核心功能
- [x] 探索任务不会立即完成
- [x] 任务状态正确流转（待执行→运行中→已完成）
- [x] 实时进度正确显示
- [x] 生成探索产物文件

### 性能指标
- [ ] 5个页面探索时间：3-5分钟
- [ ] LLM调用成功率：>95%
- [ ] 页面访问成功率：>90%

### 用户体验
- [ ] 任务中心通知友好清晰
- [ ] 进度展示实时更新
- [ ] 错误提示准确易懂
- [ ] 产物查看方便快捷

---

## 后续优化

### 优先级P0
- [ ] 添加探索中途取消功能
- [ ] 添加LLM调用重试机制
- [ ] 优化Playwright超时处理

### 优先级P1
- [ ] 添加探索成本预估
- [ ] 添加调用次数限制
- [ ] 优化进度推送频率

### 优先级P2
- [ ] 实现项目级pages管理
- [ ] 添加探索策略配置
- [ ] 优化元素提取准确度

---

**准备好后，按照上述步骤执行测试！**
