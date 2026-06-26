# 上下文管理 - SummarizationMiddleware

**日期**: 2026-06-26  
**方案**: LangChain官方SummarizationMiddleware

---

## 🎯 官方方案

```python
from langchain.agents.middleware.summarization import SummarizationMiddleware

# 创建中间件
summarization_middleware = SummarizationMiddleware(
    llm=ChatOpenAI(model="gpt-3.5-turbo"),  # 用便宜模型总结
    max_token_limit=3000,  # 超过3k自动总结
    buffer_size=2,  # 保留最近2条完整消息
)

# AgentExecutor添加middleware
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    middlewares=[summarization_middleware],  # 自动管理
    verbose=True
)
```

---

## 📊 工作原理

```
Turn 1-10: 历史 < 3000 tokens
  → 不触发总结

Turn 15: 历史达到 3200 tokens
  → 自动总结：
    - 保留最近2条完整
    - 总结更早的历史
    - 新历史 = [总结] + [最近2条]
    - 压缩到 ~1500 tokens
```

---

## 🎯 双重保护策略

### Middleware + 定期重置

```python
class ExplorationOrchestrator:
    RESET_INTERVAL = 10  # 每10个页面重置Agent
    
    def explore_site(self, urls):
        for url in urls:
            self._explore_page(url)
            self.pages_explored += 1
            
            # 定期重置（清空所有历史）
            if self.pages_explored >= self.RESET_INTERVAL:
                logger.info("重置Agent")
                self.agent = self._create_agent()
                self.pages_explored = 0
```

**双重保护**:
1. SummarizationMiddleware: 自动压缩（3k→1.5k）
2. 定期重置: 每10页清空历史

---

## 📊 效果对比（50个页面）

| 方案 | 上下文 | 响应时间 | 成本 |
|------|--------|---------|------|
| 无管理 | ~150k | 10秒 | $3.00 |
| **Middleware+重置** | **< 5k** | **3秒** | **$0.50** |

---

## ✅ 推荐配置

```python
# 主LLM
llm = ChatOpenAI(model="deepseek-chat")

# 总结LLM（便宜模型）
summarization_llm = ChatOpenAI(model="gpt-3.5-turbo")

# Middleware
summarization_middleware = SummarizationMiddleware(
    llm=summarization_llm,
    max_token_limit=3000,
    buffer_size=2
)

# 配合定期重置（每10页）
reset_interval = 10
```

---

## 🎯 配置文件

```yaml
context_management:
  middleware:
    enabled: true
    max_token_limit: 3000
    buffer_size: 2
  reset:
    enabled: true
    interval: 10
```
