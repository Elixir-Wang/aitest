#!/bin/bash

# 测试 SSE 事件推送
# 用法: ./test_sse_events.sh <project_id> <run_id>

PROJECT_ID=$1
RUN_ID=$2

if [ -z "$PROJECT_ID" ] || [ -z "$RUN_ID" ]; then
    echo "用法: $0 <project_id> <run_id>"
    exit 1
fi

echo "开始监听探索任务 SSE 事件流..."
echo "Project ID: $PROJECT_ID"
echo "Run ID: $RUN_ID"
echo "-----------------------------------"

# 使用 curl 连接 SSE 流并实时输出
curl -N -H "Accept: text/event-stream" \
     "http://localhost:8000/api/projects/${PROJECT_ID}/exploration-runs/${RUN_ID}/stream" 2>&1 | \
while IFS= read -r line; do
    if [[ $line == event:* ]]; then
        echo -e "\n\033[1;34m$line\033[0m"
    elif [[ $line == data:* ]]; then
        # 解析并美化 JSON
        json_data="${line#data: }"
        echo "$json_data" | python3 -m json.tool 2>/dev/null || echo "$line"
    else
        echo "$line"
    fi
done
