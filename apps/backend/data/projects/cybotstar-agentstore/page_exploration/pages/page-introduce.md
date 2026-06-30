# 百融百工 - 产品介绍

## 页面用途

该页面位于 `/introduce`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/introduce`
- 归一化路径：`/introduce`
- 已记录元素数：13

## 页面功能

- Logo图片（img）
- 产品手册（button）
- 立即体验按钮（button）
- 我要咨询按钮（button）
- 主标题（heading）
- 知识精准检索（region）
- Chat Flow智能编排（region）
- AI Agent核心能力（region）
- 数据分析洞察能力（region）
- 产品客服（region）
- 网站客服（region）
- 用户协议footer链接（link）
- 隐私政策footer链接（link）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| Logo图片 | img | 页面交互元素 | `getByRole('img', { name: 'Logo' })` |
| 产品手册 | button | 页面交互元素 | `getByText('产品手册')` |
| 立即体验按钮 | button | 页面交互元素 | `getByRole('button', { name: '立即体验' })` |
| 我要咨询按钮 | button | 页面交互元素 | `getByRole('button', { name: '我要咨询' })` |
| 主标题 | heading | 页面交互元素 | `getByRole('heading', { name: '首个聚焦结果交付的智能体平台，快速激活业务价值，使AI普惠千业万户' })` |
| 知识精准检索 | region | 页面交互元素 | `getByText('知识精准检索 尽在掌握')` |
| Chat Flow智能编排 | region | 页面交互元素 | `getByText('Chat Flow')` |
| AI Agent核心能力 | region | 页面交互元素 | `getByText('拥有AI Agent 核心能力')` |
| 数据分析洞察能力 | region | 页面交互元素 | `getByText('数据分析洞察能力')` |
| 产品客服 | region | 页面交互元素 | `getByRole('heading', { name: '产品客服' })` |
| 网站客服 | region | 页面交互元素 | `getByRole('heading', { name: '网站客服' })` |
| 用户协议footer链接 | link | 页面交互元素 | `getByText('用户协议').last()` |
| 隐私政策footer链接 | link | 页面交互元素 | `getByText('隐私政策').last()` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
