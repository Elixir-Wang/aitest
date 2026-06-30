# 智能体广场 - 百融百工

## 页面用途

该页面位于 `/agentstore`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/agentStore`
- 归一化路径：`/agentstore`
- 已记录元素数：17

## 页面功能

- 搜索（textbox）
- 全部（button）
- 已订阅（button）
- 最近使用（button）
- 选择语言（button）
- 按发布时间排序（button）
- 官方（button）
- 客服场景（button）
- 营销场景（button）
- 合规与风控（button）
- 金融业务（button）
- 保险场景（button）
- 产品服务（button）
- 零售场景（button）
- 人力资源（button）
- 报告生成（button）
- 其他（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 搜索 | textbox | 页面交互元素 | `getByRole('textbox', { name: '搜索' })` |
| 全部 | button | 页面交互元素 | `getByRole('button', { name: '全部' }).first()` |
| 已订阅 | button | 页面交互元素 | `getByRole('button', { name: '已订阅' })` |
| 最近使用 | button | 页面交互元素 | `getByRole('button', { name: '最近使用' })` |
| 选择语言 | button | 页面交互元素 | `getByRole('button', { name: '选择语言' })` |
| 按发布时间排序 | button | 页面交互元素 | `getByRole('button', { name: '按发布时间排序' })` |
| 官方 | button | 页面交互元素 | `getByRole('button', { name: '官方' })` |
| 客服场景 | button | 页面交互元素 | `getByRole('button', { name: '客服场景' })` |
| 营销场景 | button | 页面交互元素 | `getByRole('button', { name: '营销场景' })` |
| 合规与风控 | button | 页面交互元素 | `getByRole('button', { name: '合规与风控' })` |
| 金融业务 | button | 页面交互元素 | `getByRole('button', { name: '金融业务' })` |
| 保险场景 | button | 页面交互元素 | `getByRole('button', { name: '保险场景' })` |
| 产品服务 | button | 页面交互元素 | `getByRole('button', { name: '产品服务' })` |
| 零售场景 | button | 页面交互元素 | `getByRole('button', { name: '零售场景' })` |
| 人力资源 | button | 页面交互元素 | `getByRole('button', { name: '人力资源' })` |
| 报告生成 | button | 页面交互元素 | `getByRole('button', { name: '报告生成' })` |
| 其他 | button | 页面交互元素 | `getByRole('button', { name: '其他' })` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
