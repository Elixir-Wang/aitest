# Backend配置方案分析

## 背景

当前我们有：
- **FilesystemBackend (skills)**: 读取 Skills SKILL.md 文件
- **FilesystemBackend (workspace)**: 操作项目workspace目录
- **LocalShellBackend**: 执行shell命令
- **PlaywrightCLI**: Python subprocess直接调用playwright-cli

## 方案对比

### 方案1：保留 LocalShellBackend（当前）

```python
shell_backend = LocalShellBackend(cwd=workspace_root, env={})

composite_backend = CompositeBackend(
    default=shell_backend,
    routes={
        "/skills/": skills_backend,
        "/": workspace_backend,
    },
)
```

**优点**：
- ✅ 参考项目也这么用，架构一致
- ✅ 如果未来需要Agent直接执行shell命令，已经准备好了
- ✅ deepagents可能内部有些功能依赖shell backend
- ✅ 更灵活，Agent可以执行任意命令（如git, npm等）

**缺点**：
- ❌ 当前我们的工具都是Python封装好的，不需要Agent直接执行shell
- ❌ 安全风险：Agent理论上可以执行任意shell命令
- ❌ 多一层抽象，增加复杂度

---

### 方案2：只用 FilesystemBackend

```python
composite_backend = CompositeBackend(
    default=workspace_backend,
    routes={
        "/skills/": skills_backend,
    },
)
```

**优点**：
- ✅ 更简单，只保留必要的Backend
- ✅ 更安全，Agent无法执行任意shell命令
- ✅ 我们的工具已经封装好了playwright-cli调用

**缺点**：
- ❌ 如果未来需要Agent执行shell命令（如git操作），需要重新添加
- ❌ 与参考项目架构不一致
- ❌ 可能有未知的deepagents内部依赖

---

### 方案3：完全不用 CompositeBackend

```python
skills_middleware = SkillsMiddleware(
    backend=skills_backend,  # 直接传单个backend
    sources=["/skills/page_explorer/", "/skills/locator_best_practices/"],
)

agent = create_agent(
    model=model,
    tools=all_tools,
    system_prompt=SYSTEM_PROMPT,
    middleware=[skills_middleware, summarization_middleware],
    # 不传backend参数
)
```

**优点**：
- ✅ 最简单，只保留Skills需要的
- ✅ Agent完全通过工具操作，不直接访问文件系统

**缺点**：
- ❌ 不知道create_agent是否要求backend参数
- ❌ 与参考项目差异太大

---

## 深入分析

### 参考项目为什么用 LocalShellBackend？

让我查看参考项目的工具：

参考项目有 `execute_web_script` 工具，需要：
1. 执行 `playwright test script.spec.ts`
2. 执行 `npm install`  
3. 生成测试报告

这些都需要在shell中执行任意命令。

### 我们项目的实际需求

我们的工具：
1. `playwright_snap_tool` - ✅ PlaywrightCLI已封装
2. `playwright_navigate_tool` - ✅ PlaywrightCLI已封装
3. `playwright_click_tool` - ✅ PlaywrightCLI已封装
4. `playwright_fill_tool` - ✅ PlaywrightCLI已封装
5. `write_page_artifact_tool` - ✅ Python文件操作
6. `save_page_snapshot_tool` - ✅ Python文件操作

**结论：我们的所有操作都已经封装好，不需要Agent直接执行shell命令**

---

## 推荐方案

### 🎯 推荐：方案2（只用FilesystemBackend）

```python
# 1. 创建Backend
skills_backend = FilesystemBackend(
    root_dir=str(skills_root),
    virtual_mode=True,
)

workspace_backend = FilesystemBackend(
    root_dir=str(workspace_root),
    virtual_mode=True,
)

composite_backend = CompositeBackend(
    default=workspace_backend,
    routes={
        "/skills/": skills_backend,
    },
)

# 2. 创建Skills中间件
skills_middleware = SkillsMiddleware(
    backend=composite_backend,
    sources=["/skills/page_explorer/", "/skills/locator_best_practices/"],
)

# 3. 创建Agent
agent = create_agent(
    model=model,
    tools=all_tools,
    system_prompt=SYSTEM_PROMPT,
    middleware=[skills_middleware, summarization_middleware],
    backend=composite_backend,
)
```

### 理由：

1. **满足当前需求**
   - ✅ SkillsMiddleware需要读取Skills文件 → skills_backend
   - ✅ 未来可能需要读写workspace文件 → workspace_backend
   - ❌ 不需要执行任意shell命令 → 不需要shell_backend

2. **更安全**
   - Agent只能通过工具操作
   - 不能执行任意shell命令

3. **更简洁**
   - 少一个Backend配置
   - 代码更清晰

4. **足够灵活**
   - 如果未来真的需要shell执行，再加回来
   - 当前保留CompositeBackend结构，容易扩展

---

## 备选：方案1（保留LocalShellBackend）

如果考虑到：
- 参考项目这么用，可能有理由
- 未来可能需要（虽然目前看不到）
- 保持与参考项目架构完全一致

那就保留当前的实现不变。

---

## 我的建议

**采用方案2，删除LocalShellBackend**

原因总结：
1. 我们的PlaywrightCLI已经封装了所有playwright命令
2. 我们的工具不需要Agent直接执行shell
3. 更安全，避免Agent执行危险命令
4. 代码更简洁，容易维护
5. 如果未来需要，随时可以加回来

你觉得呢？
