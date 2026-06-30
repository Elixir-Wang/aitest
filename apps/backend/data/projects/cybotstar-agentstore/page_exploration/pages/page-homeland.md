# 空间管理 - 百融百工

## 页面用途

该页面位于 `/homeland`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/homeland`
- 归一化路径：`/homeland`
- 已记录元素数：5

## 页面功能

- 空间成员设置（button）
- 智能体设置（button）
- 空间设置（button）
- 请输入关键字查找（textbox）
- 邀请成员（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 空间成员设置 | button | 页面交互元素 | `getByRole('button', { name: '空间成员设置' })` |
| 智能体设置 | button | 页面交互元素 | `getByRole('button', { name: '智能体设置' })` |
| 空间设置 | button | 页面交互元素 | `getByRole('button', { name: '空间设置' })` |
| 请输入关键字查找 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入关键字查找' })` |
| 邀请成员 | button | 页面交互元素 | `getByRole('button', { name: '邀请成员' })` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
