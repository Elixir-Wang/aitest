# Skills 设计

**日期**: 2026-06-26  
**状态**: 2个核心Skills

---

## 🎯 Skills概述

探索Agent使用2个核心Skills：
1. **page_explorer** - 探索策略和页面分析
2. **locator_best_practices** - 定位器选择最佳实践

**不包括**: cache_strategy（缓存是纯编程逻辑，由CacheManager处理）

---

## 📍 Skills目录结构

```
apps/backend/app/agents/page_exploration/skills/
├── page_explorer/
│   └── SKILL.md
└── locator_best_practices/
    └── SKILL.md
```

---

## 📚 Skill内容

### page_explorer/SKILL.md

详见实际文件（617行），包含：
- 页面类型识别（Dashboard/List/Detail/Form/Modal）
- 导航决策框架
- 3种探索模式（CRUD/Settings/Search）
- 完整示例场景

### locator_best_practices/SKILL.md

详见实际文件，包含：
- 5级定位器优先级（Role→Label→TestId→Placeholder→Text）
- 决策树
- 常见模式
- 红旗警告

---

## ✅ 使用方式

在system_prompt中引用：
```python
SYSTEM_PROMPT = """
...
当你需要探索策略指导时，参考 {page_explorer} skill。
当你需要选择定位器时，参考 {locator_best_practices} skill。
...
"""
```
