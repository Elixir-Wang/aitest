# 智能体基础配置 - 百融百工

## 页面用途

该页面位于 `/botsetting`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。

## 页面内容

- 页面地址：`https://www.cybotstar.cn/botSetting?id=18922&tab=1`
- 归一化路径：`/botsetting`
- 已记录元素数：10

## 页面功能

- 历史版本（button）
- 发布（button）
- 基础配置（button）
- 资源配置（button）
- 高级配置（button）
- 实时互动配置（button）
- 请输入欢迎语（textbox）
- BR_LLM（button）
- AI 生成（button）
- 请输入问题，按Shift+Enter换行（textbox）

## 关键元素

| 名称 | 类型 | 作用 | 推荐定位器 |
|---|---|---|---|
| 历史版本 | button | 页面交互元素 | `getByRole('button', { name: '历史版本' })` |
| 发布 | button | 页面交互元素 | `getByRole('button', { name: '发布' })` |
| 基础配置 | button | 页面交互元素 | `getByRole('button', { name: '基础配置' })` |
| 资源配置 | button | 页面交互元素 | `getByRole('button', { name: '资源配置' })` |
| 高级配置 | button | 页面交互元素 | `getByRole('button', { name: '高级配置' })` |
| 实时互动配置 | button | 页面交互元素 | `getByRole('button', { name: '实时互动配置' })` |
| 请输入欢迎语 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入欢迎语' })` |
| BR_LLM | button | 页面交互元素 | `getByRole('button', { name: 'BR_LLM' })` |
| AI 生成 | button | 页面交互元素 | `getByRole('button', { name: 'AI 生成' })` |
| 请输入问题，按Shift+Enter换行 | textbox | 页面交互元素 | `getByRole('textbox', { name: '请输入问题，按Shift+Enter换行' })` |

## 已探索交互

| 操作 | 结果 | 状态 |
|---|---|---|
| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |

## 跳过和阻塞

- 当前产物未记录跳过操作或阻塞项。

## 测试建议

- 基于关键元素补充可见性、可点击性和主要交互流程测试。
