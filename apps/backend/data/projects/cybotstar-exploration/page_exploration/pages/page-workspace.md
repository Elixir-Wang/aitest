# 百融百工 - 工作台

## 页面用途

该页面位于 `/workspace`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/workspace`
- 归一化路径：`/workspace`
- 已记录元素数：4

## 页面功能

- 创建（button）
- 导入（button）
- 搜索智能体（textbox）
- 工作台（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 创建 | button | 页面交互元素 | `getByRole('button', { name: '创建' })` |
| 导入 | button | 页面交互元素 | `getByText('导入')` |
| 搜索智能体 | textbox | 页面交互元素 | `getByRole('textbox', { name: '搜索智能体' })` |
| 工作台 | button | 页面交互元素 | `getByRole('button', { name: '工作台' })` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
