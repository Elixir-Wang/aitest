# CybotStar - Sign Up Agent Studio

## 页面用途

该页面位于 `/login`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/login?tab=register`
- 归一化路径：`/login`
- 已记录元素数：10

## 页面功能

- Sign up Agent Studio（heading）
- Email（textbox）
- Phone Number Registration（generic）
- Graphic Verification Code（textbox）
- SMS Verification Code（textbox）
- Get Verification Code（button）
- Password（textbox）
- Confirm Password（textbox）
- Register and Sign in（button）
- Sign in（generic）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| Sign up Agent Studio | heading | 页面交互元素 | `getByText('Sign up Agent Studio')` |
| Email | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Email' })` |
| Phone Number Registration | generic | 页面交互元素 | `getByText('Phone Number Registration')` |
| Graphic Verification Code | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Verification code' })` |
| SMS Verification Code | textbox | 页面交互元素 | `getByLabel('* SMS Verification Code').getByRole('textbox')` |
| Get Verification Code | button | 页面交互元素 | `getByRole('button', { name: 'Verification Code' })` |
| Password | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Please enter a password' })` |
| Confirm Password | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Please enter the confirm password' })` |
| Register and Sign in | button | 页面交互元素 | `getByRole('button', { name: 'Register and Sign in' })` |
| Sign in | generic | 页面交互元素 | `getByText('Sign in')` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
