import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);

test("cybertron environment credentials are optional and restored when editing", () => {
  assert.match(pageSource, /cybertronRobotKey:\s*asString\(authConfig\.cybertron_robot_key\)/);
  assert.match(pageSource, /cybertronRobotToken:\s*asString\(authConfig\.cybertron_robot_token\)/);
  assert.match(pageSource, /cybertronUsername:\s*asString\(authConfig\.username\)/);
  assert.doesNotMatch(pageSource, /塞伯坦智能体必须填写/);
});

test("only cybertron key and token opt into independent password visibility controls", () => {
  assert.match(pageSource, /EyeOff/);
  assert.match(pageSource, /showCybertronRobotKey/);
  assert.match(pageSource, /showCybertronRobotToken/);
  assert.match(
    pageSource,
    /label="cybertron-robot-key"[\s\S]*?onTogglePasswordVisibility=\{\(\) =>[\s\S]*?passwordVisible=\{showCybertronRobotKey\}/,
  );
  assert.match(
    pageSource,
    /label="cybertron-robot-token"[\s\S]*?onTogglePasswordVisibility=\{\(\) =>[\s\S]*?passwordVisible=\{showCybertronRobotToken\}/,
  );
  assert.match(pageSource, /aria-label=\{`\$\{passwordVisible \? "隐藏" : "显示"\} \$\{label\}`\}/);
  assert.doesNotMatch(pageSource, /label="密码"[\s\S]{0,500}onTogglePasswordVisibility=/);
});
