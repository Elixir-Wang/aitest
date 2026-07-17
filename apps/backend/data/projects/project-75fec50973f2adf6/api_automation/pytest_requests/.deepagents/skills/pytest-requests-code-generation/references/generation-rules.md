# 生成规则

## 确定性原则

相同 endpoint 和 cases 输入必须生成相同文件 key 与内容。生成新 endpoint 不得删除其他 endpoint 制品。

## 首次执行规则

1. 创建所有层级目录和文件
2. 基础文件（`api/client.py`、`utils/`、`config/`）只生成一次
3. 每个 endpoint 创建对应的 `testcases/{module}/{feature}/` 目录

## 非首次执行规则

| 场景 | 操作 |
|------|------|
| 新增 endpoint | 在 `api/` 创建/更新 module_{module}.py，在 `testcases/` 创建功能目录 |
| 新增用例 | 在对应 `testcases/{module}/{feature}/` 下追加到 YAML |
| 修改用例 | 更新 YAML 中对应用例数据 |
| 修改断言 | 更新 YAML 中对应用例的 assertions |

## 路径规则

- 所有路径相对于项目根目录
- 不使用绝对路径
- API 模块按业务模块组织：`api/module_{module}.py`
- 测试用例按功能组织：`testcases/{module}/{feature}/`

## 导入规则

- `api/client.py` 导出基础 client
- 各 module 文件从 `api.client` 导入 session
- 测试文件从 `api.module_xxx` 导入 API 方法
- 数据加载器统一使用 `utils.data_loader`
