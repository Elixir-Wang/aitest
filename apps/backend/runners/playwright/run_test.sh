#!/bin/bash
# 运行协议点击测试
export AI_TESTING_LOGIN_USERNAME="hongbao.wang@brgroup.com"
export AI_TESTING_LOGIN_PASSWORD="test123"  # 请替换为实际密码

echo "提示: 如果需要设置密码，请修改 run_test.sh 文件"
echo ""

node test_agreement_click.mjs
