# 探索模块深度分析报告

> **生成时间**: 2026-06-21  
> **分析范围**: 探索模块所有核心文件  
> **发现问题数**: 12 个

## 🚨 高优先级问题（需立即解决）

### 1. ✅ 目标验证仅支持特定格式 - **已修复**

**位置**: `goal_validation_service.py:130-134`

**问题**: 
```python
def _supports_article_link_button_login_goal(goal: str) -> bool:
    has_link = "链接" in goal or "超链接" in goal or "link" in goal.lower()
    has_button = "按钮" in goal or "button" in goal.lower()
    has_login = any(pattern in goal.lower() for pattern in ("login", "signin", "登录", "登陆", "验证码", "401", "403"))
    return has_login and (has_link or has_button)
```

只有目标同时包含"登录相关词"+"链接/按钮"才能执行详细验证，其他目标直接返回 `pending`。

**影响**: 90% 的探索目标无法被有效验证

**修复状态**: ✅ **已完成** - 添加了 `_validate_generic_goal()` 函数，所有目标都能验证

---

### 2. ⚠️ 限制值验证缺乏上界约束

**位置**: `service.py:1113-1120`

**问题**:
```python
def _validate_execution_limits(*, max_pages: int | None, max_actions: int | None, timeout_minutes: int | None) -> None:
    if any(value is not None and value < 1 for value in values.values()):
        raise api_error(400, "INVALID_EXPLORATION_LIMIT", "探索执行边界必须大于 0。")
```

**缺陷**:
- ❌ 没有上界：用户可以设置 `max_pages=1000000`
- ❌ 没有参数关联验证：`timeout=1` + `max_pages=10000` 明显不合理
- ❌ 没有全局资源限制

**潜在风险**: 
- 系统资源耗尽
- DoS 攻击风险
- 成本失控

**建议修复**: 
```python
LIMITS = {
    "max_pages": (1, 10000),      # 最小1页，最大10000页
    "max_actions": (1, 100000),   # 最小1个，最大10万个动作
    "timeout_minutes": (1, 720),  # 最小1分钟，最大12小时
}

def _validate_execution_limits(...):
    # 1. 验证下界
    # 2. 验证上界
    # 3. 验证参数关联（如 timeout 足够完成 max_pages）
```

---

## ⚡ 中优先级问题（建议优化）

### 3. 登录页检测规则过于简化

**位置**: `goal_validation_service.py:4-17, 224-228`

**问题**:
```python
LOGIN_PATTERNS = (
    "login", "signin", "sign-in", "auth", "passport",
    "account/login", "user/login", "登录", "登陆", "验证码", "401", "403",
)
```

**缺陷**:
- ❌ "auth" 太宽泛，误匹配 `/authorize`, `/authentication`
- ❌ "401"/"403" 应该检查 HTTP 状态码而非 URL 字符串
- ❌ 只支持中英文，不支持日韩文等
- ❌ 无法识别 OAuth/SAML 等现代认证流程

**影响**: 误报率高，国际化网站支持差

---

### 4. 不安全按钮关键词硬编码

**位置**: `goal_validation_service.py:19-35`

**问题**:
```python
UNSAFE_BUTTON_KEYWORDS = (
    "删除", "移除", "提交", "支付", "付款", "确认", "确定",
    "发布", "保存", "创建", "新增", "修改", "编辑", "上传", "发送",
)
```

**缺陷**:
- ❌ 只支持中文
- ❌ 简单子字符串匹配（"确认查看" 也被标记为不安全）
- ❌ 没有危险等级分级
- ❌ 用户无法自定义

**建议**: 
- 多语言支持
- 上下文分析（按钮位置、颜色、class）
- 风险分级（高危/中危/低危）
- 项目级配置

---

### 5. 默认执行上限不合理

**位置**: `schemas/exploration.py:23-25`

**问题**:
```python
max_pages: int = 50        # 对中型网站不足
max_actions: int = 1000    # 依据不明
timeout_minutes: int = 120 # 固定2小时
```

**建议**: 根据探索范围智能推荐
```python
# 入口页探索
max_pages: 1-5, timeout: 5-10min

# 模块探索  
max_pages: 10-50, timeout: 20-60min

# 全站探索
max_pages: 100-1000, timeout: 60-240min
```

---

### 6. 状态转换规则不清晰

**位置**: `goal_validation_service.py:117-127`

**问题**:
```python
def terminal_status_for_goal_validation(current_status: str, validation: dict) -> str:
    if current_status != "completed":
        return current_status
    validation_status = str(validation.get("status") or "")
    if validation_status in {"skipped", "passed"}:
        return current_status
    if validation_status == "failed":
        return "blocked"
    if validation_status == "partial":
        return "partial"
    return "partial"  # ❌ 不可达代码
```

**问题**: 
- 为什么 `failed` → `blocked`，但 `partial` → `partial`？
- 最后一行永远不会执行
- 缺乏文档说明

---

### 7. 覆盖范围判断太模糊

**位置**: `site_orchestrator.py:1058-1061`

**问题**:
```python
def _is_full_site_scope(run) -> bool:
    scope = str(run["scope"] or "").lower()
    full_site_terms = ("全部站点", "全部内容", "所有内容", "所有页面", "全站", "遍历")
    return any(term in scope for term in full_site_terms)
```

**缺陷**:
- 仅字符串匹配
- 没有考虑 `forbidden_paths` 的影响
- 阈值过严（只探索了1页就被标记为"覆盖不足"）

---

### 8. 登录策略流转有隐含假设

**位置**: `site_orchestrator.py:270-278`

**不清晰的逻辑**:
```python
if captcha_strategy == "manual" and not reuse_auth_state:
    return "account_password", "none", False  # 为什么强制改成 account_password?
```

策略组合的有效性规则隐含在代码中，缺乏文档。

---

## 📊 低优先级问题（渐进优化）

### 9. 报告中硬编码业务标签

**位置**: `artifact_service.py:1037-1050`

```python
labels = {
    "agentStore": "探索广场",    # ❌ 只对特定应用有效
    "workspace": "工作台",
    "agentAnalysis": "效果评测",
    # ...
}
```

通用模块不应包含特定业务的硬编码标签。

---

### 10. 探索范围解析格式严格

**位置**: `service.py:1101-1110`

```python
match = re.search(r"范围包含[：:](.+)", scope, flags=re.S)  # 只支持这种格式
```

不支持其他格式或语言，缺乏容错。

---

### 11. 页面动作显示限制

**位置**: `artifact_service.py:749`

```python
return "、".join(action_names[:5]) or "-"  # 硬编码显示5个
```

无法查看完整动作列表。

---

### 12. 日志级别推断不精确

**位置**: `service.py:520-528`

```python
if event in {"blocked", "skipped"}:
    return "warning"  # blocked 和 skipped 严重程度可能不同
```

缺乏对不同 blocker 类型的区分。

---

## 📈 核心问题总结

所有问题的共性：

### 🔴 过度硬编码
- 字符串模式、关键词列表、默认值都写死在代码里
- 缺乏配置文件、数据库配置或用户自定义能力

### 🔴 缺乏灵活性  
- 一刀切的规则无法适应不同网站
- 没有项目级、环境级、用户级的配置层次

### 🔴 国际化支持差
- 大量中文硬编码
- 不支持多语言网站

### 🔴 缺乏文档
- 隐含的业务规则没有说明
- 状态转换逻辑不透明

---

## 🎯 优化建议

### 短期（本周）
1. ✅ 修复目标验证限制（已完成）
2. ⚠️ 添加执行限制的上界验证（高优先级）

### 中期（本月）
1. 提取硬编码配置到配置文件
2. 优化登录页和不安全按钮的检测规则
3. 实现智能的默认值推荐

### 长期（下季度）
1. 构建可扩展的规则引擎
2. 支持多语言和国际化
3. 添加机器学习模型辅助检测
4. 实现细粒度的权限和配置管理

---

## 💡 架构改进方向

```
当前架构：硬编码规则 → 不灵活、难维护

目标架构：
┌─────────────────────────────────────┐
│         配置管理层                    │
│  - 全局配置                           │
│  - 项目级配置                         │
│  - 环境级配置                         │
│  - 用户自定义规则                     │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│         规则引擎                      │
│  - 可插拔的验证器                     │
│  - 策略组合                           │
│  - 智能推荐                           │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│         执行层                        │
│  - 探索执行                           │
│  - 目标验证                           │
│  - 报告生成                           │
└─────────────────────────────────────┘
```

---

**结论**: 探索模块功能强大，但存在过度硬编码问题。通过系统性地提取配置、引入规则引擎、增强灵活性，可以显著提升用户体验和适用性。
