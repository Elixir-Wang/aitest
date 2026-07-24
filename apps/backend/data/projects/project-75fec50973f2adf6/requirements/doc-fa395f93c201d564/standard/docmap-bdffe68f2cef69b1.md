# LLM模型增加思考模式状态标签&开关

## 需求背景

当前在编辑Agent选用LLM模型时，无法直观查看目标模型是否支持开启思考模式；同时不支持Agent配置时自定义思考模式是否开启。

## 需求目标

1. 在模型选择处的模型名称后展示是否支持思考模式状态标签，做到状态可视化。
2. 在Agent对话模型配置弹窗内增加思考模式开关（仅支持思考模式的模型显示），支持用户手动开启/关闭思考模式。

## 需求详细描述

### 前端 - Agent 模型选择区域

模型名称后面追加标签：当模型支持思考模式时展示【Think】标签，模型若不支持思考模式则不展示标签。

![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/758cf9e0-9963-4008-b7ab-f437dcd3e7df.png)

### 支持思考模式的LLM模型，在对话模型配置弹窗内增加思考模式开启/关闭开关（不支持思考模式模型不显示该开关）

| 涉及配置项位置 | 截图 |
| --- | --- |
| 自主规划Agent - 对话模型配置弹窗 | ![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/758cf9e0-9963-4008-b7ab-f437dcd3e7df.png)![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/98134edb-63f9-4549-ab13-ca25ab6a79c0.png) |
| Multi-Agent - Agent节点 - 对话模型配置弹窗 | ![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/77258ce0-a145-46e7-bd69-c46e80770a07.png) |
| 写作Agent - 新建Agent模板 - 正文生成模型配置弹窗 | ![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/97a5f7c6-67cf-400e-8d43-1c58fdc999c0.png) |
| 对话流 - 大模型回复节点 - 大模型配置 | ![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/9ef26ee2-d86c-4a26-b483-704651be9821.png) |
| 对话流 - 大模型变量赋值节点 - 大模型配置 | ![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/9fb86c10-42b9-4ac1-b49e-7cc652514c0b.png) |
| 任务流Agent - 大模型变量赋值节点 - 大模型配置 | ![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/87f6bb13-052e-4751-a257-a26c32e35aa1.png) |

### 思考模式开启/关闭在Agent对话框内的效果

**开启思考模式效果：**

![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/20de7249-82d0-4ed9-a985-2b8456a55e46.png)

**未开启思考模式效果：**

![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/meonarbVgE4WJqXx/img/d7241802-1c92-4351-a104-b92f2bac2e53.png)
