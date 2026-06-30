# CybotStar - Login (SMS Code Tab)

## 页面用途

该页面位于 `/login`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/login?tab=sms`
- 归一化路径：`/login`
- 已记录元素数：9

## 页面功能

- Account Tab（generic）
- SMS Code Tab（generic）
- Phone Number（textbox）
- SMS Verification Code（textbox）
- Get Verification Code（button）
- Log In（button）
- User Agreement（link）
- Privacy Policy（link）
- Sign Up（generic）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| Account Tab | generic | 页面交互元素 | `getByText('Account')` |
| SMS Code Tab | generic | 页面交互元素 | `getByText('SMS Code')` |
| Phone Number | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Please enter a phone number' })` |
| SMS Verification Code | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Verification Code' })` |
| Get Verification Code | button | 页面交互元素 | `getByRole('button', { name: 'Verification Code' })` |
| Log In | button | 页面交互元素 | `getByRole('button', { name: 'Log In' })` |
| User Agreement | link | 页面交互元素 | `getByRole('link', { name: '《User Agreement》' })` |
| Privacy Policy | link | 页面交互元素 | `getByRole('link', { name: '《Privacy Policy》' })` |
| Sign Up | generic | 页面交互元素 | `getByText('Sign up')` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
