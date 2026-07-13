# Learnings

## [LRN-20260713-001] correction

**Logged**: 2026-07-13T19:40:00+08:00
**Priority**: high
**Status**: resolved
**Area**: requirements

### Summary
对话流长文本需求中的10,000和20,000均为变量长度规则，不是请求或用户输入长度限制。

### Details
- 变量长度小于等于10,000字符时不外置，超过10,000字符时外置。
- 单个普通文本变量最大长度为20,000字符。
- 用户消息、API请求或节点输入不存在独立的20,000字符请求长度限制。
- 当内容被节点写入变量时，才执行变量长度校验。

### Source
- User correction

### Tags
requirements, long-text, variable-length, correction

## [LRN-20260713-002] correction

**Logged**: 2026-07-13T19:50:00+08:00
**Priority**: high
**Status**: resolved
**Area**: requirements

### Summary
20,000字符仅作为变量长度兜底配置，不需要设计超过20,000字符的业务测试场景。

### Details
- 超过10,000字符后变量已经进入外置存储流程。
- 测试重点是10,000字符外置边界、外置后的传递与消费、页面分块展示。
- 20,000字符只验证兜底配置不影响外置逻辑。
- 不生成20,001字符及以上测试点。

### Source
- User correction

### Tags
requirements, long-text, boundary, correction
