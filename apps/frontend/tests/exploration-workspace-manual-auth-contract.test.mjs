import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const workspaceSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-workspace.tsx", import.meta.url),
  "utf8",
);

test("manual auth controls require the saved environment to enable manual captcha", () => {
  assert.match(
    workspaceSource,
    /function isManualAuthEnabled\(environment: ExplorationEnvironment \| null\)[\s\S]*environment\.login_strategy === "account_password"[\s\S]*environment\.captcha_strategy === "manual"[\s\S]*environment\.reuse_auth_state/,
  );
  assert.match(
    workspaceSource,
    /const showManualAuthControls =[\s\S]*savedManualAuthEnabled && selectedManualCaptcha && formMatchesSavedManualAuthConfig\(editingEnvironment, form\)/,
  );
});

test("saving a manual captcha environment keeps the login controls available immediately", () => {
  assert.match(
    workspaceSource,
    /setEditingEnvironment\(updated\);[\s\S]*setForm\(formFromEnvironment\(updated\)\);[\s\S]*if \(isManualAuthEnabled\(updated\)\) {[\s\S]*toast\.success\("环境已更新，可打开登录窗口保存登录态"\);[\s\S]*return;/,
  );
  assert.match(
    workspaceSource,
    /if \(isManualAuthEnabled\(created\)\) {[\s\S]*setEditingEnvironment\(created\);[\s\S]*setForm\(formFromEnvironment\(created\)\);[\s\S]*toast\.success\("环境已创建，可打开登录窗口保存登录态"\);[\s\S]*return;/,
  );
});

test("ended manual auth sessions clear pending save and cancel controls", () => {
  assert.match(
    workspaceSource,
    /const manualAuthSessionActive = isActiveManualAuthSession\(manualAuthSession\);[\s\S]*if \(!editingEnvironment \|\| !manualAuthSessionActive \|\| !manualAuthSession\) {[\s\S]*manual-auth\/\$\{manualAuthSession\.session_id\}\/status/,
  );
  assert.match(
    workspaceSource,
    /if \(isManualAuthSessionEnded\(session\)\) {[\s\S]*completeManualAuthSession\(session, environmentId\);[\s\S]*return;/,
  );
  assert.match(
    workspaceSource,
    /if \(result\.status === "ended"\) {[\s\S]*setManualAuthSession\(null\);[\s\S]*syncManualAuthState\(result, editingEnvironment\.id\);[\s\S]*return;/,
  );
  assert.match(workspaceSource, /"auto_saved"/);
  assert.match(
    workspaceSource,
    /if \(session\.status === "auto_saved"\) {[\s\S]*toast\.success\(session\.message \|\| "登录态已自动保存"\);/,
  );
});

test("credential status is based on saved credentials", () => {
  assert.match(
    workspaceSource,
    /const hasReusableEnvironmentPassword =[\s\S]*editingEnvironment\?\.login_strategy === "account_password" && editingEnvironment\.has_saved_credentials;/,
  );
  assert.doesNotMatch(workspaceSource, /password_mask/);
  assert.doesNotMatch(workspaceSource, /item\.has_saved_credentials \? "可自动填充" : "需保存密码"/);
});

test("manual auth action buttons stay on one row on wide dialogs", () => {
  assert.match(
    workspaceSource,
    /className="flex shrink-0 flex-wrap gap-2 lg:flex-nowrap lg:justify-end"/,
  );
  assert.match(workspaceSource, /className="whitespace-nowrap"[\s\S]*打开登录/);
  assert.match(workspaceSource, /className="whitespace-nowrap"[\s\S]*保存登录态/);
  assert.match(workspaceSource, /className="whitespace-nowrap"[\s\S]*取消/);
});

test("exploration workspace does not expose execution or interaction modes", () => {
  assert.doesNotMatch(workspaceSource, /explorationExecutionModeOptions/);
  assert.doesNotMatch(workspaceSource, /explorationInteractionModeOptions/);
  assert.doesNotMatch(workspaceSource, /executionMode/);
  assert.doesNotMatch(workspaceSource, /interactionMode/);
  assert.doesNotMatch(workspaceSource, /execution_mode/);
  assert.doesNotMatch(workspaceSource, /interaction_mode/);
  assert.doesNotMatch(workspaceSource, /agent_turn_count/);
  assert.doesNotMatch(workspaceSource, />执行模式</);
  assert.doesNotMatch(workspaceSource, />探索引擎</);
  assert.doesNotMatch(workspaceSource, />交互策略</);
});
