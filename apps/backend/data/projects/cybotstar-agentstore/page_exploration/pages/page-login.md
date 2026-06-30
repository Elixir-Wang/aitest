# 百融百工 - 登录页

## 页面用途

该页面位于 `/login`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/login`
- 归一化路径：`/login`
- 已记录元素数：11

## 页面功能

- 账号密码登录tab（tab）
- 短信验证登录tab（tab）
- 账号输入框（textbox）
- 密码输入框（textbox）
- 图形验证码输入框（textbox）
- 忘记密码链接（link）
- 登录按钮（button）
- 用户协议链接（link）
- 隐私政策链接（link）
- 去注册链接（link）
- 语言切换器（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 账号密码登录tab | tab | 页面交互元素 | `getByRole('tab', { name: '账号密码' })` |
| 短信验证登录tab | tab | 页面交互元素 | `getByRole('tab', { name: '短信验证' })` |
| 账号输入框 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入邮箱/手机号' })` |
| 密码输入框 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入密码' })` |
| 图形验证码输入框 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入图形验证码' })` |
| 忘记密码链接 | link | 页面交互元素 | `getByText('忘记密码?')` |
| 登录按钮 | button | 页面交互元素 | `getByRole('button', { name: '登录' })` |
| 用户协议链接 | link | 页面交互元素 | `getByRole('link', { name: '《用户协议》' })` |
| 隐私政策链接 | link | 页面交互元素 | `getByRole('link', { name: '《隐私政策》' })` |
| 去注册链接 | link | 页面交互元素 | `getByText('去注册')` |
| 语言切换器 | button | 页面交互元素 | `getByText('简体中文')` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
