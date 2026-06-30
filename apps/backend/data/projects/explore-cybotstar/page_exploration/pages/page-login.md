# CybotStar - Login Page

## 页面用途

该页面位于 `/login`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/login`
- 归一化路径：`/login`
- 已记录元素数：13

## 页面功能

- 账号登录（tab）
- 短信验证码登录（tab）
- 邮箱账号（textbox）
- 密码（textbox）
- 验证码（textbox）
- 密码可见性切换（button）
- 忘记密码（link）
- 登录（button）
- 用户协议勾选（checkbox）
- 用户协议（link）
- 隐私政策（link）
- 注册账号（link）
- 语言切换（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 账号登录 | tab | 页面交互元素 | `getByRole('generic', { name: 'Account' })` |
| 短信验证码登录 | tab | 页面交互元素 | `getByRole('generic', { name: 'SMS Code' })` |
| 邮箱账号 | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Email' })` |
| 密码 | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Enter your password' })` |
| 验证码 | textbox | 页面交互元素 | `getByRole('textbox', { name: 'Verification code' })` |
| 密码可见性切换 | button | 页面交互元素 | `getByRole('img').filter({ hasNot: page.getByRole('button') })` |
| 忘记密码 | link | 页面交互元素 | `getByText('Forgot password?')` |
| 登录 | button | 页面交互元素 | `getByRole('button', { name: 'Log In' })` |
| 用户协议勾选 | checkbox | 页面交互元素 | `getByRole('paragraph').first()` |
| 用户协议 | link | 页面交互元素 | `getByRole('link', { name: '《User Agreement》' })` |
| 隐私政策 | link | 页面交互元素 | `getByRole('link', { name: '《Privacy Policy》' })` |
| 注册账号 | link | 页面交互元素 | `getByText('Sign up')` |
| 语言切换 | button | 页面交互元素 | `getByText('English')` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
