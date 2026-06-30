# 百融百工 - 注册

## 页面用途

该页面位于 `/login`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/login`
- 归一化路径：`/login`
- 已记录元素数：9

## 页面功能

- 邮箱输入框（textbox）
- 使用手机号注册（generic）
- 图形验证码（textbox）
- 邮箱验证码（textbox）
- 获取验证码（button）
- 注册密码（textbox）
- 确认密码（textbox）
- 注册并登录（button）
- 去登录（generic）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 邮箱输入框 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入邮箱' })` |
| 使用手机号注册 | generic | 页面交互元素 | `getByText('或使用手机号注册')` |
| 图形验证码 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入图形验证码' })` |
| 邮箱验证码 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入邮箱验证码' })` |
| 获取验证码 | button | 页面交互元素 | `getByRole('button', { name: '获取验证码' })` |
| 注册密码 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入密码' })` |
| 确认密码 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入确认密码' })` |
| 注册并登录 | button | 页面交互元素 | `getByRole('button', { name: '注册并登录' })` |
| 去登录 | generic | 页面交互元素 | `getByText('去登录')` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
