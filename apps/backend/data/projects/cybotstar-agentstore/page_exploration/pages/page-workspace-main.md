# 工作台 - 百融百工

## 页面用途

该页面位于 `/workspace`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/workspace`
- 归一化路径：`/workspace`
- 已记录元素数：19

## 页面功能

- 创建智能体（button）
- 探索广场（button）
- 批量任务（button）
- 工作台（button）
- 资源库（button）
- 效果评测（button）
- 发布管理（button）
- 线上观测（button）
- 自动优化（button）
- 空间管理（button）
- 文档中心（button）
- 搜索智能体（textbox）
- 全部（button）
- 按创建时间排序（button）
- 创建（button）
- 分析（button）
- 使用（button）
- 对话历史（button）
- 12条/页（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 创建智能体 | button | 页面交互元素 | `getByRole('button', { name: '创建智能体' })` |
| 探索广场 | button | 页面交互元素 | `getByRole('button', { name: '探索广场' })` |
| 批量任务 | button | 页面交互元素 | `getByRole('button', { name: '批量任务' })` |
| 工作台 | button | 页面交互元素 | `getByRole('button', { name: '工作台' })` |
| 资源库 | button | 页面交互元素 | `getByRole('button', { name: '资源库' })` |
| 效果评测 | button | 页面交互元素 | `getByRole('button', { name: '效果评测' })` |
| 发布管理 | button | 页面交互元素 | `getByRole('button', { name: '发布管理' })` |
| 线上观测 | button | 页面交互元素 | `getByRole('button', { name: '线上观测' })` |
| 自动优化 | button | 页面交互元素 | `getByRole('button', { name: '自动优化' })` |
| 空间管理 | button | 页面交互元素 | `getByRole('button', { name: '空间管理' })` |
| 文档中心 | button | 页面交互元素 | `getByRole('button', { name: '文档中心' })` |
| 搜索智能体 | textbox | 页面交互元素 | `getByRole('textbox', { name: '搜索智能体' })` |
| 全部 | button | 页面交互元素 | `getByRole('button', { name: '全部' }).first()` |
| 按创建时间排序 | button | 页面交互元素 | `getByRole('button', { name: '按创建时间排序' })` |
| 创建 | button | 页面交互元素 | `getByRole('button', { name: '创建' })` |
| 分析 | button | 页面交互元素 | `getByRole('button', { name: '分析' }).first()` |
| 使用 | button | 页面交互元素 | `getByRole('button', { name: '使用' }).first()` |
| 对话历史 | button | 页面交互元素 | `getByRole('button', { name: '对话历史' }).first()` |
| 12条/页 | button | 页面交互元素 | `getByRole('button', { name: '12条/页' })` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
