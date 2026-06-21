# 测试用例示例

本文档提供了不同类型测试用例的示例，供参考。

## 功能测试示例

### 登录功能

```json
{
  "id": "tc-001",
  "module": "登录模块",
  "title": "使用正确的用户名和密码登录",
  "priority": "P0",
  "type": "功能测试",
  "precondition": "用户已注册且状态为启用",
  "steps": [
    "打开登录页面",
    "在用户名输入框输入 'test@example.com'",
    "在密码输入框输入正确的密码",
    "点击'登录'按钮"
  ],
  "expected_result": "登录成功，页面跳转到首页，右上角显示用户昵称，用户状态变为'已登录'",
  "test_data": "用户名: test@example.com, 密码: Test123\!",
  "notes": ""
}
```

## 异常测试示例

### 登录失败

```json
{
  "id": "tc-002",
  "module": "登录模块",
  "title": "使用错误的密码登录",
  "priority": "P0",
  "type": "异常测试",
  "precondition": "用户已注册",
  "steps": [
    "打开登录页面",
    "在用户名输入框输入 'test@example.com'",
    "在密码输入框输入错误的密码",
    "点击'登录'按钮"
  ],
  "expected_result": "登录失败，页面显示错误提示'用户名或密码错误'，停留在登录页面，登录失败次数+1",
  "test_data": "用户名: test@example.com, 错误密码: wrong123",
  "notes": "连续失败3次应锁定账户"
}
```

### 网络异常

```json
{
  "id": "tc-015",
  "module": "订单模块",
  "title": "提交订单时网络超时",
  "priority": "P1",
  "type": "异常测试",
  "precondition": "用户已登录，购物车有商品",
  "steps": [
    "进入购物车页面",
    "点击'去结算'按钮",
    "填写收货地址",
    "选择支付方式",
    "模拟网络超时（断网或设置超时时间为1ms）",
    "点击'提交订单'按钮"
  ],
  "expected_result": "显示错误提示'网络连接超时，请稍后重试'，订单未创建，购物车数据保留",
  "test_data": "",
  "notes": "需要测试环境支持网络模拟"
}
```

## 边界测试示例

### 输入长度

```json
{
  "id": "tc-025",
  "module": "用户管理",
  "title": "创建用户名长度为1个字符",
  "priority": "P2",
  "type": "边界测试",
  "precondition": "管理员已登录",
  "steps": [
    "进入用户管理页面",
    "点击'新建用户'按钮",
    "在用户名输入框输入单个字符 'a'",
    "填写其他必填项",
    "点击'保存'按钮"
  ],
  "expected_result": "根据业务规则：如果允许1字符，则创建成功；如果最小长度>1，则显示'用户名长度不能少于X个字符'",
  "test_data": "用户名: a",
  "notes": "需要确认业务规则中用户名的最小长度"
}
```

### 库存临界值

```json
{
  "id": "tc-030",
  "module": "订单模块",
  "title": "购买库存为0的商品",
  "priority": "P0",
  "type": "边界测试",
  "precondition": "商品库存为0",
  "steps": [
    "打开商品详情页",
    "尝试点击'加入购物车'按钮"
  ],
  "expected_result": "按钮显示为灰色不可点击状态，提示'该商品暂无库存'",
  "test_data": "商品ID: prod-123, 库存: 0",
  "notes": ""
}
```

## 性能测试示例

### 并发操作

```json
{
  "id": "tc-040",
  "module": "订单模块",
  "title": "100个用户同时下单",
  "priority": "P1",
  "type": "性能测试",
  "precondition": "有100个测试用户，每个用户购物车有商品",
  "steps": [
    "使用性能测试工具（如JMeter）",
    "配置100个并发用户",
    "每个用户同时执行下单操作",
    "记录响应时间和成功率"
  ],
  "expected_result": "所有订单在3秒内完成，成功率100%，库存扣减正确无超卖",
  "test_data": "并发用户数: 100",
  "notes": "需要性能测试环境和工具"
}
```

## 安全测试示例

### 权限验证

```json
{
  "id": "tc-050",
  "module": "用户管理",
  "title": "普通用户访问管理员功能",
  "priority": "P0",
  "type": "安全测试",
  "precondition": "以普通用户身份登录",
  "steps": [
    "获取管理员功能的URL（如 /admin/users）",
    "在浏览器中直接访问该URL"
  ],
  "expected_result": "返回403禁止访问，显示'无权限访问'提示，并记录安全日志",
  "test_data": "普通用户ID: user-123",
  "notes": ""
}
```

### 数据隔离

```json
{
  "id": "tc-055",
  "module": "订单模块",
  "title": "用户A查看用户B的订单",
  "priority": "P0",
  "type": "安全测试",
  "precondition": "用户A和用户B都已登录，用户B有订单",
  "steps": [
    "以用户A身份登录",
    "获取用户B的订单ID",
    "在浏览器中访问 /orders/{用户B的订单ID}"
  ],
  "expected_result": "返回403禁止访问或404未找到，不显示用户B的订单信息",
  "test_data": "用户A: user-a-123, 用户B: user-b-456, 订单ID: order-789",
  "notes": ""
}
```

## 兼容测试示例

### 浏览器兼容

```json
{
  "id": "tc-060",
  "module": "登录模块",
  "title": "在Chrome浏览器中登录",
  "priority": "P1",
  "type": "兼容测试",
  "precondition": "已安装Chrome浏览器（最新版本）",
  "steps": [
    "使用Chrome浏览器打开登录页面",
    "输入正确的用户名和密码",
    "点击'登录'按钮"
  ],
  "expected_result": "登录成功，页面显示正常，无样式错误或功能异常",
  "test_data": "浏览器: Chrome 120.0",
  "notes": "需要测试主流浏览器：Chrome、Firefox、Safari、Edge"
}
```
