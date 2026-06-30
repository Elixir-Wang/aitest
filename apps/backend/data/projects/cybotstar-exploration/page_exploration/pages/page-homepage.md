# CybotStar - Homepage

## 页面用途

该页面位于 `/introduce`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/introduce`
- 归一化路径：`/introduce`
- 已记录元素数：15

## 页面功能

- Header Logo（img）
- Product Manual Link（link）
- Try Now Header Link（link）
- Main Page Heading（heading）
- Try Now CTA Button（button）
- Consult Button（button）
- Knowledge Retrieval Feature Section（region）
- Chat Flow Feature Section（region）
- AI Agent Feature Section（region）
- Data Analytics Feature Section（region）
- Product Service Scenario（heading）
- Website Service Scenario（heading）
- User Agreement Link（link）
- Privacy Policy Link（link）
- Contact Email（generic）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| Header Logo | img | 页面交互元素 | `getByRole('img', { name: 'Header Logo' })` |
| Product Manual Link | link | 页面交互元素 | `getByText('产品手册')` |
| Try Now Header Link | link | 页面交互元素 | `getByText('立即体验').first()` |
| Main Page Heading | heading | 页面交互元素 | `getByRole('heading', { name: '首个聚焦结果交付的智能体平台，快速激活业务价值，使AI普惠千业万户' })` |
| Try Now CTA Button | button | 页面交互元素 | `getByRole('button', { name: '立即体验' })` |
| Consult Button | button | 页面交互元素 | `getByRole('button', { name: '我要咨询' })` |
| Knowledge Retrieval Feature Section | region | 页面交互元素 | `getByText('知识精准检索 尽在掌握')` |
| Chat Flow Feature Section | region | 页面交互元素 | `getByText('Chat Flow')` |
| AI Agent Feature Section | region | 页面交互元素 | `getByText('拥有AI Agent 核心能力')` |
| Data Analytics Feature Section | region | 页面交互元素 | `getByText('数据分析洞察能力')` |
| Product Service Scenario | heading | 页面交互元素 | `getByRole('heading', { name: '产品客服' })` |
| Website Service Scenario | heading | 页面交互元素 | `getByRole('heading', { name: '网站客服' })` |
| User Agreement Link | link | 页面交互元素 | `getByText('用户协议')` |
| Privacy Policy Link | link | 页面交互元素 | `getByText('隐私政策')` |
| Contact Email | generic | 页面交互元素 | `getByText('联系我们：rc_agentos@brgroup.com')` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
