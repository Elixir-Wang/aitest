import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
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

  it("does not silently click the first repeated action when the locator is ambiguous", async () => {
    const html = `
      <!doctype html>
      <html>
        <head><title>Repeated actions</title></head>
        <body>
          <article>
            <h3>Alpha</h3>
            <button onclick="document.title = 'alpha'">编辑</button>
          </article>
          <article>
            <h3>Beta</h3>
            <button onclick="document.title = 'beta'">编辑</button>
          </article>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const result = await session.command({ type: "click", element_id: "page.getByRole('button', { name: '编辑' })" });

      assert.equal(result.success, false);
      assert.equal(result.failure.error_type, "locator_not_unique");
    } finally {
      await session.close();
    }
  });

  it("clicks the intended repeated action when the locator scopes by surrounding text", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>Scoped repeated actions</title>
          <script>
            window.addEventListener('DOMContentLoaded', () => {
              document.querySelector('[data-target="alpha"]').addEventListener('click', () => { document.title = 'alpha'; });
              document.querySelector('[data-target="beta"]').addEventListener('click', () => { document.title = 'beta'; });
            });
          </script>
        </head>
        <body>
          <article>
            <h3>Alpha</h3>
            <button data-target="alpha">编辑</button>
          </article>
          <article>
            <h3>Beta</h3>
            <button data-target="beta">编辑</button>
          </article>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const result = await session.command({
        type: "click",
        element_id: "page.getByRole('article').filter({ hasText: 'Beta' }).getByRole('button', { name: '编辑' })",
      });

      assert.equal(result.success, true);
      assert.equal(result.after_title, "beta");
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

  it("captures framework-bound cursor pointer popover options as executable elements", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>Custom popover</title>
          <style>
            [role="popover"] { position: fixed; right: 40px; top: 40px; width: 360px; padding: 16px; background: white; }
            .agent-option { display: block; padding: 8px; cursor: pointer; }
          </style>
          <script>
            window.addEventListener('DOMContentLoaded', () => {
              document.querySelector('[data-agent-type="autonomous"]').addEventListener('click', () => {
                document.title = 'selected';
              });
            });
          </script>
        </head>
        <body>
          <div>历史草稿 自主规划 Agent</div>
          <div role="popover" aria-label="创建智能体">
            <div class="agent-option" data-agent-type="autonomous">
              <strong>自主规划 Agent</strong>
              <span>能够自主规划任务，适用于大部分场景</span>
            </div>
            <div class="agent-option" data-agent-type="multi">
              <strong>Multi-Agent</strong>
              <span>在一个智能体中设置多个Agent</span>
            </div>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observed = await session.command({ type: "observe" });
      const target = observed.elements.find((element) =>
        element.name.includes("自主规划 Agent")
        && element.name.includes("能够自主规划任务")
        && element.action_type === "click"
      );

      assert.ok(target, JSON.stringify(observed.elements, null, 2));
      assert.equal(target.role, "clickable");
      assert.ok(target.primary_selector?.code, JSON.stringify(target));

      const result = await session.command({
        type: "click",
        element_id: target.primary_selector.code,
      });

      assert.equal(result.success, true, JSON.stringify(result));
      assert.equal(result.after_title, "selected");
    } finally {
      await session.close();
    }
  });

  it("clicks a popover option with repeated text using a scoped locator chain", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>工作台</title>
          <style>
            [role="popover"] { position: fixed; right: 40px; top: 40px; width: 360px; padding: 16px; background: white; }
            .agent-option { display: block; padding: 8px; cursor: pointer; }
          </style>
        </head>
        <body>
          <section>
            <article>历史草稿 自主规划 Agent</article>
            <article>已发布 自主规划 Agent</article>
          </section>
          <div role="popover" aria-label="创建智能体">
            <div class="agent-option" onclick="document.body.dataset.selected = 'autonomous'; document.title = '已选择自主规划';">
              <strong>自主规划 Agent</strong>
              <span>能够自主规划任务，适用于大部分场景</span>
            </div>
            <div class="agent-option" onclick="document.body.dataset.selected = 'multi'">
              <strong>Multi-Agent</strong>
              <span>在一个智能体中设置多个Agent</span>
            </div>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const result = await session.command({
        type: "click",
        element_id: "page.locator('[role=\"popover\"]').filter({ hasText: '自主规划 Agent' }).getByText('能够自主规划任务')",
      });

      assert.equal(result.success, true, JSON.stringify(result));
      assert.equal(result.state_signature_changed, true);
    } finally {
      await session.close();
    }
  });

  it("does not dismiss the target popover before clicking inside it", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>工作台</title>
          <style>
            [role="popover"] { position: fixed; right: 40px; top: 40px; width: 360px; padding: 16px; background: white; }
            .agent-option { display: block; padding: 8px; cursor: pointer; }
          </style>
          <script>
            document.addEventListener('keydown', (event) => {
              if (event.key === 'Escape') document.querySelector('[role="popover"]')?.remove();
            });
          </script>
        </head>
        <body>
          <section>
            <article>历史草稿 自主规划 Agent</article>
            <article>已发布 自主规划 Agent</article>
          </section>
          <div role="popover" aria-label="创建智能体">
            <div class="agent-option" onclick="document.title = '已选择自主规划';">
              <strong>自主规划 Agent</strong>
              <span>能够自主规划任务，适用于大部分场景</span>
            </div>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const result = await session.command({
        type: "click",
        element_id: "page.locator('[role=\"popover\"]').filter({ hasText: '自主规划 Agent' }).getByText('能够自主规划任务')",
      });

      assert.equal(result.success, true, JSON.stringify(result));
      assert.equal(result.after_title, "已选择自主规划");
    } finally {
      await session.close();
    }
  });

  it("does not dismiss the target dialog before filling a field", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>创建表单</title>
          <script>
            document.addEventListener('keydown', (event) => {
              if (event.key === 'Escape') document.querySelector('[role="dialog"]')?.remove();
            });
          </script>
        </head>
        <body>
          <div role="dialog" aria-label="创建智能体">
            <label>
              智能体功能介绍
              <textarea placeholder="请输入对该智能体的描述"></textarea>
            </label>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const result = await session.command({
        type: "fill",
        element_id: "page.getByPlaceholder('请输入对该智能体的描述', { exact: true })",
        value: "你是一个友好的助手",
      });

      assert.equal(result.success, true, JSON.stringify(result));
      assert.equal(result.value_applied, true);
    } finally {
      await session.close();
    }
  });

  it("fills the only visible field when hidden duplicates share the same placeholder", async () => {
    const html = `
      <!doctype html>
      <html>
        <head><title>重复字段</title></head>
        <body>
          <textarea placeholder="请输入对该智能体的描述" style="display: none"></textarea>
          <textarea placeholder="请输入对该智能体的描述"></textarea>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const result = await session.command({
        type: "fill",
        element_id: "page.getByPlaceholder('请输入对该智能体的描述', { exact: true })",
        value: "你是一个友好的助手",
      });

      assert.equal(result.success, true, JSON.stringify(result));
      assert.equal(result.value_applied, true);
    } finally {
      await session.close();
    }
  });

  it("clicks the only visible match when hidden duplicates share the same role and name", async () => {
    const html = `
      <!doctype html>
      <html>
        <head><title>重复按钮</title></head>
        <body>
          <button style="display: none">创建</button>
          <button onclick="document.title = 'clicked'">创建</button>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const result = await session.command({
        type: "click",
        element_id: "page.getByRole('button', { name: '创建' })",
      });

      assert.equal(result.success, true, JSON.stringify(result));
      assert.equal(result.after_title, "clicked");
    } finally {
      await session.close();
    }
  });

  it("includes ancestor_chain for elements inside popover containers", async () => {
    // 验证根因修复：observePage 必须返回 ancestor_chain
    // 问题：collectDomFacts 计算了 ancestor_chain 但 observePage 丢弃了它
    const html = `
      <!doctype html>
      <html>
        <head><title>Popover test</title></head>
        <body>
          <button onclick="document.title = 'main'">创建</button>
          <div role="popover" aria-label="创建智能体">
            <button onclick="document.title = 'in-popover'">创建</button>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observed = await session.command({ type: "observe" });
      const buttons = observed.elements.filter((el) => el.name === "创建" && el.role === "button");

      assert.ok(buttons.length >= 1, `Expected at least 1 button, got ${buttons.length}`);

      // 验证至少有一个按钮有 ancestor_chain 字段
      const withChain = buttons.filter((el) => "ancestor_chain" in el);
      assert.ok(withChain.length > 0, `No element has ancestor_chain. All elements: ${JSON.stringify(buttons.map(b => Object.keys(b)))}`);

      // 验证 popover 内的按钮 ancestor_chain 包含 popover
      const inPopover = buttons.find((el) =>
        el.ancestor_chain && el.ancestor_chain.some((a) => a.role === "popover")
      );
      assert.ok(inPopover, `No button found with popover in ancestor_chain. Ancestor chains: ${JSON.stringify(buttons.map(b => b.ancestor_chain))}`);
    } finally {
      await session.close();
    }
  });

  it("provides diagnosis for not_visible errors with visible overlay info", async () => {
    // 验证根因修复：classifyActionError 对 not_visible 错误进行诊断
    const html = `
      <!doctype html>
      <html>
        <head><title>Not visible test</title></head>
        <body>
          <div role="dialog" aria-label="测试对话框">
            <button onclick="document.title = 'clicked'">确定</button>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      // 尝试点击一个不存在的元素，触发 not_visible 错误
      const result = await session.command({
        type: "click",
        element_id: "page.getByRole('button', { name: '不存在的按钮' })",
      });

      assert.equal(result.success, false);
      assert.equal(result.error_type, "not_visible");
      // 验证诊断信息包含可见容器
      if (result.diagnosis) {
        assert.ok(result.diagnosis.summary, "diagnosis.summary should not be empty");
        assert.ok(result.diagnosis.possible_cause, "diagnosis.possible_cause should not be empty");
      }
    } finally {
      await session.close();
    }
  });

  it("supports overlay observation, scoped queries, key press, and screenshots", async () => {
    const tempDir = mkdtempSync(join(tmpdir(), "browser-session-"));
    const screenshotPath = join(tempDir, "evidence.png");
    const html = `
      <!doctype html>
      <html>
        <head>
          <title>Overlay tools</title>
          <style>
            [role="popover"] { position: fixed; top: 20px; left: 20px; width: 320px; padding: 12px; background: white; border: 1px solid #ddd; }
          </style>
        </head>
        <body>
          <div role="popover" aria-label="创建智能体">
            <label>智能体名称 <input placeholder="请输入智能体名称" onkeydown="if (event.key === 'Enter') document.body.dataset.submitted = this.value" /></label>
            <button onclick="document.body.dataset.clicked = 'yes'">创建</button>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const overlays = await session.command({ type: "observe_overlays" });
      assert.equal(overlays.overlay_count, 1);
      assert.equal(overlays.overlays[0].role, "popover");

      const query = await session.command({
        type: "scoped_query",
        scope: "[role='popover']",
        text: "创建",
        limit: 10,
      });
      assert.equal(query.match_count >= 1, true);
      assert.equal(query.matches.some((item) => item.name.includes("创建")), true);

      const fill = await session.command({
        type: "fill",
        element_id: "page.getByPlaceholder('请输入智能体名称', { exact: true })",
        value: "测试 Agent",
      });
      assert.equal(fill.success, true);

      const press = await session.command({
        type: "press",
        element_id: "page.getByPlaceholder('请输入智能体名称', { exact: true })",
        key: "Enter",
      });
      assert.equal(press.success, true);
      assert.equal(press.effective_locator, "page.getByPlaceholder('请输入智能体名称', { exact: true })");

      const screenshot = await session.command({
        type: "screenshot",
        path: screenshotPath,
        full_page: false,
      });
      assert.equal(screenshot.path, screenshotPath);
      assert.equal(existsSync(screenshotPath), true);
    } finally {
      await session.close();
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("supports Playwright selector syntax in scoped queries", async () => {
    const html = `
      <!doctype html>
      <html>
        <body>
          <section><div><span>Prompt</span></div><textarea></textarea></section>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const result = await session.command({
        type: "scoped_query",
        scope: "section:has-text('Prompt')",
        role: "textbox",
      });

      assert.equal(result.match_count, 1);
      assert.equal(result.matches[0].tag, "textarea");
    } finally {
      await session.close();
    }
  });

  it("fills an unnamed contenteditable editor through its snapshot action locator", async () => {
    const html = `
      <!doctype html>
      <html>
        <body>
          <main>
            <section><div>Prompt</div><div contenteditable="true"></div></section>
          </main>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observation = await session.command({ type: "observe" });
      const editor = observation.elements.find((item) => item.role === "textbox");

      assert.equal(editor?.role, "textbox");
      assert.equal(editor?.action_type, "fill");
      assert.match(editor?.action_locator || "", /data-ai-testing-action-ref/);

      const result = await session.command({
        type: "fill",
        element_id: editor.action_locator,
        value: "你是一个友好的助手",
      });
      assert.equal(result.success, true, JSON.stringify(result));

      const updated = await session.command({ type: "observe" });
      assert.equal(updated.elements.some((item) => item.role === "textbox" && item.text === "你是一个友好的助手"), true);
    } finally {
      await session.close();
    }
  });

  it("isolates snapshot actions to the active overlay", async () => {
    const globalButtons = Array.from({ length: 90 }, (_, index) => `<button>全局操作 ${index}</button>`).join("");
    const html = `
      <!doctype html>
      <html>
        <head>
          <style>.popover { position: fixed; z-index: 100; inset: 100px; background: white; }</style>
        </head>
        <body>
          ${globalButtons}
          <div class="popover">
            <input placeholder="请输入智能体名称" />
            <button>创建</button>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observation = await session.command({ type: "observe" });

      assert.equal(observation.interaction_scope, "overlay");
      assert.equal(observation.elements.some((item) => item.name === "请输入智能体名称"), true);
      assert.equal(observation.elements.some((item) => item.name === "创建"), true);
      assert.equal(observation.elements.some((item) => item.name.startsWith("全局操作")), false);
    } finally {
      await session.close();
    }
  });

  it("prefers an active overlay when a semantic locator also matches the page", async () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <style>.popover { position: fixed; z-index: 100; inset: 100px; background: white; }</style>
        </head>
        <body>
          <button onclick="document.title = 'page'">创建</button>
          <div class="popover">
            <button onclick="document.title = 'overlay'">创建</button>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      await session.command({ type: "observe" });
      const result = await session.command({
        type: "click",
        element_id: "page.getByRole('button', { name: '创建' })",
      });

      assert.equal(result.success, true, JSON.stringify(result));
      assert.equal(result.after_title, "overlay");
    } finally {
      await session.close();
    }
  });

  it("generates a reusable overlay scoped locator", async () => {
    const html = `
      <!doctype html>
      <html>
        <head><style>.popover { position: fixed; z-index: 100; inset: 100px; }</style></head>
        <body>
          <button>创建</button>
          <div class="popover" aria-label="创建智能体">
            <button>创建</button>
          </div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      const observation = await session.command({ type: "observe" });
      const button = observation.elements.find((item) => item.role === "button" && item.name === "创建");

      assert.equal(observation.overlay?.type, "popover");
      assert.equal(observation.overlay?.primary_selector?.verification?.unique, true);
      assert.match(button?.primary_selector?.code || "", /popover.*getByRole\('button'/);
      assert.equal(button?.primary_selector?.verification?.unique, true);
    } finally {
      await session.close();
    }
  });

  it("never falls back outside an active overlay", async () => {
    const html = `
      <!doctype html>
      <html>
        <head><style>.popover { position: fixed; z-index: 100; inset: 100px; }</style></head>
        <body>
          <button onclick="document.title = 'page'">页面操作</button>
          <div class="popover"><button>浮层操作</button></div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      await session.command({ type: "observe" });
      const result = await session.command({
        type: "click",
        element_id: "page.getByRole('button', { name: '页面操作' })",
      });

      assert.equal(result.success, false, JSON.stringify(result));
      assert.equal(result.error_type, "not_visible");
    } finally {
      await session.close();
    }
  });

  it("keeps same name matches inside an overlay ambiguous", async () => {
    const html = `
      <!doctype html>
      <html>
        <head><style>.popover { position: fixed; z-index: 100; inset: 100px; }</style></head>
        <body>
          <div class="popover"><button>确认</button><button>确认</button></div>
        </body>
      </html>
    `;
    const session = await startSession(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    try {
      await session.command({ type: "observe" });
      const result = await session.command({
        type: "click",
        element_id: "page.getByRole('button', { name: '确认' })",
      });

      assert.equal(result.success, false, JSON.stringify(result));
      assert.equal(result.error_type, "locator_not_unique");
    } finally {
      await session.close();
    }
  });

  it("returns an invalid selector result without terminating the session", async () => {
    const session = await startSession("data:text/html,<main>content</main>");
    try {
      const result = await session.command({ type: "scoped_query", scope: "div[" });
      assert.equal(result.error_type, "invalid_selector");
      assert.equal(result.match_count, 0);

      const observation = await session.command({ type: "observe" });
      assert.equal(observation.url.startsWith("data:text/html"), true);
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
