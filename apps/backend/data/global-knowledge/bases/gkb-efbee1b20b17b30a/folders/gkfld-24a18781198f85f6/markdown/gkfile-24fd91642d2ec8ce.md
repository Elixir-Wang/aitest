---
schema: rejected-test-case-library/v1
project_id: project-75fec50973f2adf6
project_name: 百工平台
requirement_id: doc-72daf0a769501ca1
requirement_name: 对话流超长文本性能优化
updated_at: '2026-07-26T02:25:09.508245+00:00'
---

# 对话流超长文本性能优化

百工平台 · **3 条有效反馈**

<!-- rejected_case:start {"record_id":"rjc-e882594b8081e3af","schema":"v1"} -->
<!-- rejected_case:data {"record_id":"rjc-e882594b8081e3af","status":"active","project_id":"project-75fec50973f2adf6","project_name":"百工平台","requirement_id":"doc-72daf0a769501ca1","requirement_name":"对话流超长文本性能优化","requirement_version_id":"docver-87f3b665436b854b","requirement_version_no":4,"generation_run_id":"tcgr-580c3241fac88370","test_case_set_id":"tcs-dfea1ac5acca8fae","test_case_id":"tcs-dfea1ac5acca8fae-tc-001","title":"大模型变量赋值输出超长文本触发外置存储与引用透传","module":"信息加工-大模型变量赋值","priority":"P0","preconditions":"对话流已配置大模型变量赋值节点，且大模型输出文本长度超过10000字符。","steps":[{"action":"配置大模型变量赋值节点，使大模型输出文本长度超过10000字符","expected_result":"节点配置完成，大模型可生成超长文本输出。"},{"action":"触发对话流执行，大模型变量赋值节点开始运行","expected_result":"大模型生成超长文本输出。"},{"action":"检查大模型变量赋值节点输出处理逻辑","expected_result":"系统检测到输出文本长度超过10000字符，触发超长文本外置存储流程。"},{"action":"验证完整文本内容已存入数据库","expected_result":"数据库中存储了完整的超长文本内容，且生成了对应的唯一内容ID。"},{"action":"验证对话流运行态中变量携带的是chunk引用信息而非完整文本","expected_result":"运行态变量中不包含完整文本，只包含引用信息（内容ID、chunk总数、每chunk长度）。"},{"action":"下游节点读取该变量","expected_result":"下游节点通过统一变量读取方法，根据引用信息从数据库按chunk顺序读取并拼接完整文本，成功获取完整内容。"}],"expected_result":"大模型变量赋值输出超长文本时，完整文本存入数据库，运行态只传递chunk引用信息，下游节点按需自动还原完整内容。","reason_type":"其他","reason":"不采纳","handling":"warning_only","correction":"不采纳","reviewed_by":"u-admin","reviewed_at":"2026-07-26T02:25:09.507995+00:00","deactivated_at":""} -->
## 1. 大模型变量赋值输出超长文本触发外置存储与引用透传

有效 · 信息加工-大模型变量赋值 · P0 · V4

> **不采纳原因：** 不采纳
<!-- rejected_case:end -->

<!-- rejected_case:start {"record_id":"rjc-43b9656bc034413c","schema":"v1"} -->
<!-- rejected_case:data {"record_id":"rjc-43b9656bc034413c","status":"active","project_id":"project-75fec50973f2adf6","project_name":"百工平台","requirement_id":"doc-72daf0a769501ca1","requirement_name":"对话流超长文本性能优化","requirement_version_id":"docver-87f3b665436b854b","requirement_version_no":4,"generation_run_id":"tcgr-580c3241fac88370","test_case_set_id":"tcs-dfea1ac5acca8fae","test_case_id":"tcs-dfea1ac5acca8fae-tc-005","title":"下游节点仅判断展示时无需读取完整文本","module":"信息加工-大模型变量赋值","priority":"P1","preconditions":"对话流已配置大模型变量赋值节点输出超长文本（>10000字符），且下游节点仅需判断或展示变量值。","steps":[{"action":"触发对话流执行，大模型变量赋值节点输出超长文本并触发外置存储","expected_result":"完整文本存入数据库，运行态变量携带chunk引用信息。"},{"action":"下游节点（如条件判断节点）读取该变量进行判断","expected_result":"下游节点根据节点类型，仅读取必要的引用信息或部分内容即可完成判断，无需读取完整文本。"},{"action":"下游节点（如文本回复节点）展示该变量","expected_result":"展示节点按需读取完整文本内容进行展示。"}],"expected_result":"下游节点根据节点类型决定是否读取完整内容，仅判断展示的节点可避免读取完整文本以提升性能。","reason_type":"其他","reason":"无","handling":"warning_only","correction":"无","reviewed_by":"u-admin","reviewed_at":"2026-07-24T11:16:44.407267+00:00","deactivated_at":""} -->
## 2. 下游节点仅判断展示时无需读取完整文本

有效 · 信息加工-大模型变量赋值 · P1 · V4

> **不采纳原因：** 未提供具体原因。
<!-- rejected_case:end -->

<!-- rejected_case:start {"record_id":"rjc-e837f132c57e14a6","schema":"v1"} -->
<!-- rejected_case:data {"record_id":"rjc-e837f132c57e14a6","status":"active","project_id":"project-75fec50973f2adf6","project_name":"百工平台","requirement_id":"doc-72daf0a769501ca1","requirement_name":"对话流超长文本性能优化","requirement_version_id":"docver-3785fc6a3a10bfe4","requirement_version_no":1,"generation_run_id":"tcgr-b21b763a6a4b8e03","test_case_set_id":"tcs-0019343cc4bd2b61","test_case_id":"tcs-0019343cc4bd2b61-tc-014","title":"超长文本先触发外置存储再触发兜底限制","module":"字段长度兜底限制","priority":"P1","preconditions":"节点输出字段长度超过20000字符。","steps":[{"action":"节点输出长度超过20000字符的文本","expected_result":"系统先尝试外置存储，但因超过20000字符兜底限制，按兜底规则处理。"}],"expected_result":"超过20000字符的字段按兜底限制处理。","reason_type":"其他","reason":"不会超过20000字符，这个一般不会触发","handling":"warning_only","correction":"不会超过20000字符，这个一般不会触发","reviewed_by":"u-admin","reviewed_at":"2026-07-24T11:15:44.552295+00:00","deactivated_at":""} -->
## 3. 超长文本先触发外置存储再触发兜底限制

有效 · 字段长度兜底限制 · P1 · V1

> **不采纳原因：** 不会超过20000字符，这个一般不会触发
<!-- rejected_case:end -->
