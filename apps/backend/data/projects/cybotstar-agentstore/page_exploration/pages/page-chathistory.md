# 对话历史 - 百融百工

## 页面用途

该页面位于 `/chathistory`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/chatHistory?id=18922`
- 归一化路径：`/chathistory`
- 已记录元素数：9

## 页面功能

- 用户名（button）
- 来源（button）
- 管理员反馈（button）
- Agent跳转（button）
- 开始日期（textbox）
- 结束日期（textbox）
- 请输入关键字查找（textbox）
- 导出（button）
- 10条/页（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 用户名 | button | 页面交互元素 | `getByRole('button', { name: '用户名' })` |
| 来源 | button | 页面交互元素 | `getByRole('button', { name: '来源' })` |
| 管理员反馈 | button | 页面交互元素 | `getByRole('button', { name: '管理员反馈' })` |
| Agent跳转 | button | 页面交互元素 | `getByRole('button', { name: 'Agent跳转' })` |
| 开始日期 | textbox | 页面交互元素 | `getByRole('textbox', { name: '开始日期' })` |
| 结束日期 | textbox | 页面交互元素 | `getByRole('textbox', { name: '结束日期' })` |
| 请输入关键字查找 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入关键字查找' })` |
| 导出 | button | 页面交互元素 | `getByRole('button', { name: '导出' })` |
| 10条/页 | button | 页面交互元素 | `getByRole('button', { name: '10条/页' })` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
