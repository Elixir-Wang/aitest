# CybotStar - Product Manual (Quick Start)

## 页面用途

该页面位于 `/document/manual/82`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/document/manual/82/`
- 归一化路径：`/document/manual/82`
- 已记录元素数：11

## 页面功能

- Quick Start Heading（heading）
- Create Agent Heading（heading）
- Configure Agent Heading（heading）
- Configure Model Heading（heading）
- Role Setting Heading（heading）
- Add Skill Heading（heading）
- Add Knowledge Heading（heading）
- Add Function Heading（heading）
- Publish Agent Heading（heading）
- Workspace Mention（strong）
- Breadcrumb Product Manual（generic）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| Quick Start Heading | heading | 页面交互元素 | `getByRole('heading', { name: '快速开始' }).last()` |
| Create Agent Heading | heading | 页面交互元素 | `getByRole('heading', { name: '创建智能体' })` |
| Configure Agent Heading | heading | 页面交互元素 | `getByRole('heading', { name: '配置并调试智能体' })` |
| Configure Model Heading | heading | 页面交互元素 | `getByRole('heading', { name: '配置模型' })` |
| Role Setting Heading | heading | 页面交互元素 | `getByRole('heading', { name: '角色设定' }).last()` |
| Add Skill Heading | heading | 页面交互元素 | `getByRole('heading', { name: '为智能体添加技能（可选）' })` |
| Add Knowledge Heading | heading | 页面交互元素 | `getByRole('heading', { name: '添加知识' })` |
| Add Function Heading | heading | 页面交互元素 | `getByRole('heading', { name: '添加功能' })` |
| Publish Agent Heading | heading | 页面交互元素 | `getByRole('heading', { name: '发布智能体' })` |
| Workspace Mention | strong | 页面交互元素 | `getByText('工作台')` |
| Breadcrumb Product Manual | generic | 页面交互元素 | `getByText('产品手册').last()` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
