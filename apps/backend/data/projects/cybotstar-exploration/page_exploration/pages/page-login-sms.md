# CybotStar - Login (SMS Code)

## 页面用途

该页面位于 `/login`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/login?sms`
- 归一化路径：`/login`
- 已记录元素数：10

## 页面功能

- Account Login Tab（button）
- SMS Code Login Tab（button）
- Phone Number Input（textbox）
- SMS Code Input（textbox）
- Send SMS Code Button（button）
- Log In Button（button）
- Sign Up Link（link）
- User Agreement Link（link）
- Privacy Policy Link（link）
- Language Switcher（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| Account Login Tab | button | 页面交互元素 | `getByRole('button', { name: 'Account' })` |
| SMS Code Login Tab | button | 页面交互元素 | `getByRole('button', { name: 'SMS Code' })` |
| Phone Number Input | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Please enter a phone number' })` |
| SMS Code Input | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Verification Code' }).last()` |
| Send SMS Code Button | button | 页面交互元素 | `getByRole('button', { name: 'Verification Code' }).last()` |
| Log In Button | button | 页面交互元素 | `getByRole('button', { name: 'Log In' })` |
| Sign Up Link | link | 页面交互元素 | `getByText('Sign up')` |
| User Agreement Link | link | 页面交互元素 | `getByRole('link', { name: '《User Agreement》' })` |
| Privacy Policy Link | link | 页面交互元素 | `getByRole('link', { name: '《Privacy Policy》' })` |
| Language Switcher | button | 页面交互元素 | `getByText('English')` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
