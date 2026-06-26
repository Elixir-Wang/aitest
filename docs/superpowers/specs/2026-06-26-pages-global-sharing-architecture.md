# Pages 全局共享架构

**日期**: 2026-06-26  
**核心**: 项目级Pages，跨run复用

---

## 🎯 核心设计

### Pages存储位置

```
data/projects/{project_id}/page_exploration/
├── pages/                              # ✅ 项目级，全局复用
│   ├── page-workspace-agents.yaml
│   └── page-workspace-settings.yaml
├── cache_index.yaml                    # 项目级缓存索引
└── runs/{run_id}/
    ├── run.yaml                        # 配置 + 统计
    ├── discovered_pages.yaml           # 引用项目级pages
    └── graph.yaml                      # 本次探索的页面关系
```

---

## ✅ 核心优势

1. **跨run复用** - 所有探索run共享同一份pages
2. **跨环境复用** - 测试/生产/本地环境共用
3. **易于维护** - 页面变化只需更新一个文件
4. **节省存储** - 不再重复存储相同页面

---

## 📋 缓存机制

### cache_index.yaml

```yaml
pages:
  - normalized_path: "/workspace/agents"
    page_id: "page-workspace-agents"
    page_file: "pages/page-workspace-agents.yaml"
    last_explored_at: "2026-06-26T11:00:00Z"
    last_run_id: "run-001"
    last_environment: "test"
```

### 工作流程

1. 探索前：检查cache_index
2. 缓存命中：复用pages产物
3. 缓存未命中：探索并写入pages/
4. 更新cache_index

---

## 🔧 URL归一化

```python
# 运行时拼接完整URL
ENV_BASE_URLS = {
    'prod': 'https://prod.example.com',
    'test': 'https://test.example.com',
}

def get_full_url(normalized_path: str, environment: str) -> str:
    base_url = ENV_BASE_URLS[environment]
    return base_url + normalized_path
```

不在pages产物中存储env_urls，避免环境无限增长。
