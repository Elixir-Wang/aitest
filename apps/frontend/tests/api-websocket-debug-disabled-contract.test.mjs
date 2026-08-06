import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const apiPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);

test("websocket endpoint debug action is disabled with an explicit unsupported message", () => {
  assert.match(
    apiPageSource,
    /const isWebSocketEndpoint = activeEndpoint \? endpointProtocol\(activeEndpoint\) === "websocket" : false/,
  );
  assert.match(apiPageSource, /disabled=\{isWebSocketEndpoint/);
  assert.match(apiPageSource, /title=\{isWebSocketEndpoint \? "WebSocket 调试暂未支持" : "打开接口调试"\}/);
  assert.match(apiPageSource, /isWebSocketEndpoint \? "暂不支持调试" : "测试一下"/);
  assert.doesNotMatch(apiPageSource, /role="status"/);
});
