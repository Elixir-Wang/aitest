# 智能体市场

## 页面用途

该页面位于 `/agentstore`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/agentStore`
- 归一化路径：`/agentstore`
- 已记录元素数：17

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
- 搜索（textbox）
- 全部（button）
- 已订阅（button）
- 最近使用（button）
- 按发布时间排序（button）
- 官方（button）

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
| 搜索 | textbox | 页面交互元素 | `getByRole('textbox', { name: '搜索' })` |
| 全部 | button | 页面交互元素 | `getByRole('button', { name: '全部', exact: true })` |
| 已订阅 | button | 页面交互元素 | `getByRole('button', { name: '已订阅' })` |
| 最近使用 | button | 页面交互元素 | `getByRole('button', { name: '最近使用' })` |
| 按发布时间排序 | button | 页面交互元素 | `getByRole('button', { name: '按发布时间排序' })` |
| 官方 | button | 页面交互元素 | `getByRole('button', { name: '官方' })` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
