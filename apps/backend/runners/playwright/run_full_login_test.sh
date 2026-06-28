#!/bin/bash
# 完整登录流程测试启动脚本

echo "================================================================"
echo "🚀 完整登录流程测试 - 有头模式"
echo "================================================================"
echo ""
echo "此测试将执行以下步骤："
echo "  1. 访问登录页面"
echo "  2. 填写账号密码"
echo "  3. 显示验证码图片"
echo "  4. 等待您手动输入验证码"
echo "  5. 使用修复后的逻辑勾选协议"
echo "  6. 提交登录"
echo "  7. 检查登录结果"
echo ""
echo "================================================================"
echo ""

# 检查是否设置了环境变量
if [ -z "$AI_TESTING_LOGIN_USERNAME" ]; then
    echo "❌ 请先设置环境变量 AI_TESTING_LOGIN_USERNAME"
    echo ""
    echo "运行方式："
    echo "  export AI_TESTING_LOGIN_USERNAME='hongbao.wang@brgroup.com'"
    echo "  export AI_TESTING_LOGIN_PASSWORD='你的密码'"
    echo "  ./run_full_login_test.sh"
    echo ""
    exit 1
fi

if [ -z "$AI_TESTING_LOGIN_PASSWORD" ]; then
    echo "❌ 请先设置环境变量 AI_TESTING_LOGIN_PASSWORD"
    echo ""
    echo "运行方式："
    echo "  export AI_TESTING_LOGIN_USERNAME='hongbao.wang@brgroup.com'"
    echo "  export AI_TESTING_LOGIN_PASSWORD='你的密码'"
    echo "  ./run_full_login_test.sh"
    echo ""
    exit 1
fi

echo "✅ 环境变量已设置"
echo "   用户名: $AI_TESTING_LOGIN_USERNAME"
echo "   密码: ********"
echo ""
echo "按回车键开始测试..."
read

# 运行测试
node test_full_login.mjs
