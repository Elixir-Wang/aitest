# 探索终止逻辑

**日期**: 2026-06-26  
**核心**: Agent如何知道何时停止探索

---

## 🎯 终止条件（满足任一即停止）

### 1. 目标达成终止
```python
if exploration_queue.is_empty():
    stop_reason = "all_pages_explored"
    terminate()
```

### 2. 达到限制终止
- 页面数量达到上限（max_pages）
- 探索时间达到上限（max_duration）
- 探索深度达到上限（max_depth）

### 3. 错误终止
- 连续失败次数过多（max_consecutive_failures）
- Agent无法继续（unrecoverable_error）

### 4. 手动终止
- 用户主动停止

---

## 🔄 URL队列管理

```python
class ExplorationQueue:
    def __init__(self, start_url, scope):
        self.queue = deque([start_url])
        self.explored = set()
    
    def add_url(self, url):
        normalized = normalize_url(url)
        if normalized in self.explored:
            return False
        if not self._in_scope(url):
            return False
        self.queue.append(url)
        return True
    
    def pop(self):
        return self.queue.popleft() if not self.is_empty() else None
```

---

## 📊 配置示例

```yaml
exploration_config:
  max_pages: 50
  max_depth: 3
  max_duration_minutes: 30
  max_consecutive_failures: 3
```

---

## 🔄 循环检测

- URL归一化（去除query和fragment）
- 已探索集合（避免重复）
- 深度跟踪
- 限制同一路径的变体数量
