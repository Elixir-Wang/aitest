# 资源库-卡片 - 百融百工

## 页面用途

该页面位于 `/resource`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/resource?space=space&tab=card`
- 归一化路径：`/resource`
- 已记录元素数：8

## 页面功能

- 请输入关键词搜索（textbox）
- 知识库（button）
- 数据库（button）
- 插件库（button）
- 声纹组（button）
- 卡片（button）
- 批量操作（button）
- 添加资源（button）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 请输入关键词搜索 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入关键词搜索' })` |
| 知识库 | button | 页面交互元素 | `getByRole('button', { name: '知识库' })` |
| 数据库 | button | 页面交互元素 | `getByRole('button', { name: '数据库' })` |
| 插件库 | button | 页面交互元素 | `getByRole('button', { name: '插件库' })` |
| 声纹组 | button | 页面交互元素 | `getByRole('button', { name: '声纹组' })` |
| 卡片 | button | 页面交互元素 | `getByRole('button', { name: '卡片' })` |
| 批量操作 | button | 页面交互元素 | `getByRole('button', { name: '批量操作' })` |
| 添加资源 | button | 页面交互元素 | `getByRole('button', { name: '添加资源' })` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
