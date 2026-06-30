# CybotStar - Sign Up

## 页面用途

该页面位于 `/login`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/login`
- 归一化路径：`/login`
- 已记录元素数：13

## 页面功能

- Sign Up Agent Studio Title（heading）
- Sign Up Email Input（textbox）
- Phone Number Registration Link（link）
- Graphic Verification Code Input（textbox）
- SMS Verification Code Input（textbox）
- Send SMS Code Button（button）
- Sign Up Password Input（textbox）
- Sign Up Confirm Password Input（textbox）
- Register and Sign In Button（button）
- User Agreement Link（link）
- Privacy Policy Link（link）
- Sign In Link（link）
- Language Switcher（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| Sign Up Agent Studio Title | heading | 页面交互元素 | `getByText('Sign up Agent Studio')` |
| Sign Up Email Input | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Email' }).last()` |
| Phone Number Registration Link | link | 页面交互元素 | `getByText('or usePhone Number Registration')` |
| Graphic Verification Code Input | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Verification code' }).first()` |
| SMS Verification Code Input | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Verification Code' }).last()` |
| Send SMS Code Button | button | 页面交互元素 | `getByRole('button', { name: 'Verification Code' })` |
| Sign Up Password Input | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Please enter a password' })` |
| Sign Up Confirm Password Input | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Please enter the confirm password' })` |
| Register and Sign In Button | button | 页面交互元素 | `getByRole('button', { name: 'Register and Sign in' })` |
| User Agreement Link | link | 页面交互元素 | `getByRole('link', { name: '《User Agreement》' })` |
| Privacy Policy Link | link | 页面交互元素 | `getByRole('link', { name: '《Privacy Policy》' })` |
| Sign In Link | link | 页面交互元素 | `getByText('Sign in')` |
| Language Switcher | button | 页面交互元素 | `getByText('English')` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
