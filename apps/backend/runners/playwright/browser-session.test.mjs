import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { describe, it } from "node:test";

describe("browser session observation", () => {
  it("captures clickable menu divs without inventing button role locators", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>百融百工</title>
          <style>
            .menu-content { width: 180px; height: 32px; display: flex; align-items: center; }
            .menu-name { margin-left: 8px; }
          </style>
        </head>
        <body>
          <aside>
            <div class="menu-content" onclick="location.hash = 'workspace'">
              <span class="icon"></span>
              <span class="menu-name">工作台</span>
            </div>
          </aside>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observed = await session.command({ type: "observe" });
      const workspace = observed.elements.find((element) => element.name === "工作台");

      assert.ok(workspace);
      assert.equal(workspace.role, "clickable");
      assert.equal(workspace.action_type, "click");
      assert.equal(workspace.risk_hint, "safe");
      assert.equal(workspace.primary_selector.kind, "text");
      assert.equal(workspace.primary_selector.verification.unique, true);
      assert.equal(workspace.primary_selector.verification.visible, true);
      assert.doesNotMatch(workspace.primary_selector.code, /getByRole\('button'/);
      assert.equal(workspace.fallback_selector.kind, "css");
    } finally {
      await session.close();
    }
  });

  it("dismisses transient overlays before clicking the target", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>Overlay click</title>
          <style>
            #overlay { position: fixed; inset: 0; z-index: 10; background: rgba(0, 0, 0, 0.01); }
            button { margin-top: 80px; }
          </style>
          <script>
            document.addEventListener('keydown', (event) => {
              if (event.key === 'Escape') document.getElementById('overlay')?.remove();
            });
          </script>
        </head>
        <body>
          <div id="overlay"></div>
          <button onclick="document.body.dataset.clicked = 'yes'">使用</button>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observed = await session.command({ type: "observe" });
      const target = observed.elements.find((element) => element.name === "使用");
      assert.ok(target);

      const result = await session.command({ type: "click", element_id: target.primary_selector.code });

      assert.equal(result.status, "passed");
      assert.equal(result.error_type, "");
    } finally {
      await session.close();
    }
  });

  it("clicks the interactive ancestor for readonly combobox inputs", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>Combobox click</title>
          <style>
            .select-shell { width: 240px; height: 36px; display: inline-flex; align-items: center; }
            input { width: 1px; opacity: 0.01; }
          </style>
        </head>
        <body>
          <div class="select-shell" role="combobox" tabindex="0" aria-label="指标" onclick="document.body.dataset.open = 'yes'">
            <input role="combobox" readonly aria-label="指标" />
            <span>提问次数 & 访问人数</span>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observed = await session.command({ type: "observe" });
      const target = observed.elements.find((element) => element.role === "combobox");
      assert.ok(target);

      const result = await session.command({ type: "click", element_id: target.primary_selector.code });

      assert.equal(result.status, "passed");
      assert.equal(result.error_type, "");
    } finally {
      await session.close();
    }
  });

  it("prefers contextual semantic selectors for repeated card action buttons", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>工作台</title>
          <style>
            .agent-card { display: inline-block; width: 280px; padding: 16px; margin: 8px; border: 1px solid #ddd; }
            .actions { margin-top: 16px; }
            .actions button { margin-right: 8px; }
          </style>
        </head>
        <body>
          <article class="agent-card">
            <h3>无插件智能体2</h3>
            <div class="actions">
              <button>分析</button>
              <button>使用</button>
              <button>对话历史</button>
            </div>
          </article>
          <article class="agent-card">
            <h3>测试_自主规划智能体</h3>
            <div class="actions">
              <button>分析</button>
              <button>使用</button>
              <button>对话历史</button>
            </div>
          </article>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observed = await session.command({ type: "observe" });
      const target = observed.elements.find((element) => element.name === "对话历史" && element.context?.container_name === "测试_自主规划智能体");

      assert.ok(target);
      assert.equal(target.primary_selector.kind, "contextual");
      assert.match(target.primary_selector.code, /测试_自主规划智能体/);
      assert.notEqual(target.primary_selector.kind, "css");
    } finally {
      await session.close();
    }
  });

  it("captures popover content in the semantic snapshot fallbacks", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>工作台</title>
          <style>
            .popover { position: fixed; right: 40px; top: 40px; width: 360px; padding: 16px; background: white; }
            .agent-option { display: flex; gap: 8px; padding: 8px; }
          </style>
        </head>
        <body>
          <button>创建</button>
          <div class="popover">
            <div>创建智能体</div>
            <div class="agent-option"><strong>自主规划 Agent</strong><span>能够自主规划任务，适用于大部分场景</span></div>
            <div class="agent-option"><strong>Multi-Agent</strong><span>在一个智能体中设置多个Agent</span></div>
            <div class="agent-option"><strong>写作 Agent</strong><span>完成复杂写作内容生成</span></div>
            <div class="agent-option"><strong>任务流 Agent</strong><span>面向自动化任务</span></div>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observed = await session.command({ type: "observe" });
      const axNames = observed.accessibility_tree.map((node) => node.name).filter(Boolean);

      assert.ok(observed.accessibility_tree.length > 0);
      assert.ok(axNames.includes("创建"));
      assert.ok(observed.visible_text_blocks.includes("创建智能体"));
      assert.ok(observed.visible_text_blocks.includes("自主规划 Agent"));
      assert.ok(observed.visible_text_blocks.includes("Multi-Agent"));
    } finally {
      await session.close();
    }
  });
});

async function startSession(url) {
  const child = spawn("node", ["browser-session.mjs", url, "chrome", ""], {
    cwd: new URL(".", import.meta.url),
    stdio: ["pipe", "pipe", "pipe"],
  });
  const reader = lineReader(child);
  const started = await reader.nextMessage();
  assert.equal(started.kind, "session_started");
  return {
    async command(payload) {
      child.stdin.write(`${JSON.stringify({ id: "cmd-observe", ...payload })}\n`);
      const response = await reader.nextMessage("cmd-observe");
      assert.equal(response.status, "ok", response.error || "browser session command failed");
      return response.result;
    },
    async close() {
      if (child.exitCode !== null) {
        return;
      }
      child.stdin.write(`${JSON.stringify({ id: "cmd-finish", type: "finish" })}\n`);
      child.stdin.end();
      await reader.nextMessage("cmd-finish").catch(() => null);
      await waitForExit(child, 3000);
    },
  };
}

function lineReader(child) {
  let buffer = "";
  const queue = [];
  const waiters = [];
  let stderr = "";
  child.stdout.on("data", (chunk) => {
    buffer += chunk.toString();
    let newlineIndex;
    while ((newlineIndex = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (!line) continue;
      const message = JSON.parse(line);
      const waiterIndex = waiters.findIndex((waiter) => !waiter.id || waiter.id === message.id);
      if (waiterIndex >= 0) {
        waiters.splice(waiterIndex, 1)[0].resolve(message);
      } else {
        queue.push(message);
      }
    }
  });
  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });
  child.once("exit", () => {
    for (const waiter of waiters.splice(0)) {
      waiter.reject(new Error(stderr || "browser session exited before response"));
    }
  });
  return {
    nextMessage(id = "") {
      const existingIndex = queue.findIndex((message) => !id || message.id === id);
      if (existingIndex >= 0) {
        return Promise.resolve(queue.splice(existingIndex, 1)[0]);
      }
      return new Promise((resolve, reject) => waiters.push({ id, resolve, reject }));
    },
  };
}

async function waitForExit(child, timeoutMs) {
  if (child.exitCode !== null) {
    return;
  }
  const exited = await Promise.race([
    new Promise((resolve) => child.once("exit", () => resolve(true))),
    new Promise((resolve) => setTimeout(() => resolve(false), timeoutMs)),
  ]);
  if (!exited && child.exitCode === null) {
    child.kill("SIGTERM");
    await Promise.race([
      new Promise((resolve) => child.once("exit", resolve)),
      new Promise((resolve) => setTimeout(resolve, 1000)),
    ]);
  }
}
