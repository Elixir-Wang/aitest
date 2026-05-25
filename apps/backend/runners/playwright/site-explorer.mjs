import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const [, , startUrl, artifactRoot, channel = "", forbiddenInput = ""] = process.argv;

if (!startUrl || !artifactRoot) {
  console.error("Usage: node site-explorer.mjs <startUrl> <artifactRoot> [channel]");
  process.exit(2);
}

const maxPages = Number(process.env.AI_TESTING_EXPLORATION_MAX_PAGES || "8");
const maxActions = Number(process.env.AI_TESTING_EXPLORATION_MAX_ACTIONS || "20");
const navigationTimeout = Number(process.env.AI_TESTING_EXPLORATION_NAV_TIMEOUT_MS || "10000");

const dirs = {
  screenshots: path.join(artifactRoot, "screenshots"),
  snapshots: path.join(artifactRoot, "snapshots"),
};

for (const dir of Object.values(dirs)) {
  await fs.mkdir(dir, { recursive: true });
}

const browser = await chromium.launch({
  channel: channel || undefined,
  headless: true,
});

const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  ignoreHTTPSErrors: true,
});
const page = await context.newPage();
page.setDefaultTimeout(navigationTimeout);
page.setDefaultNavigationTimeout(navigationTimeout);

const start = new URL(startUrl);
const visited = new Set();
const queued = [start.href];
const pages = [];
const elements = [];
const blockers = [];
let actionCount = 0;
const forbiddenTerms = forbiddenInput
  .split(/[\n,，;；]+/)
  .map((item) => item.trim().toLowerCase())
  .filter(Boolean);

try {
  while (queued.length > 0 && pages.length < maxPages && actionCount < maxActions) {
    const targetUrl = queued.shift();
    if (!targetUrl || visited.has(normalizeUrl(targetUrl))) {
      continue;
    }
    visited.add(normalizeUrl(targetUrl));

    try {
      await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle", { timeout: navigationTimeout }).catch(() => {});
    } catch (error) {
      blockers.push({
        page_ref: targetUrl,
        reason_type: "navigation_failed",
        reason: String(error?.message || error),
        suggested_action: "检查页面路由、网络连通性、登录状态或证书配置后重试。",
      });
      continue;
    }

    const pageIndex = pages.length + 1;
    const slug = `page-${String(pageIndex).padStart(2, "0")}`;
    const screenshotFile = path.join(dirs.screenshots, `${slug}.png`);
    const snapshotFile = path.join(dirs.snapshots, `${slug}.html`);
    await page.screenshot({ path: screenshotFile, fullPage: true }).catch(() => {});
    await fs.writeFile(snapshotFile, await page.content(), "utf-8");

    const facts = await page.evaluate(() => {
      const visible = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
      };
      const labelOf = (el) => {
        const aria = el.getAttribute("aria-label");
        const title = el.getAttribute("title");
        const placeholder = el.getAttribute("placeholder");
        const text = el.innerText || el.textContent;
        const value = el.getAttribute("value");
        return (aria || title || placeholder || text || value || el.name || el.id || el.tagName).trim().replace(/\s+/g, " ").slice(0, 120);
      };
      const cssPath = (el) => {
        if (el.id) return `#${CSS.escape(el.id)}`;
        const testId = el.getAttribute("data-testid") || el.getAttribute("data-test");
        if (testId) return `[data-testid="${CSS.escape(testId)}"]`;
        const name = el.getAttribute("name");
        if (name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
        return el.tagName.toLowerCase();
      };
      const elementFacts = Array.from(document.querySelectorAll("a,button,input,textarea,select,[role='button'],[role='link']"))
        .filter(visible)
        .slice(0, 80)
        .map((el, index) => ({
          index,
          name: labelOf(el),
          type: el.tagName.toLowerCase() === "a" ? "link" : el.tagName.toLowerCase(),
          inputType: el.getAttribute("type") || "",
          locator: cssPath(el),
          href: el.href || "",
        }));
      const headings = Array.from(document.querySelectorAll("h1,h2,h3"))
        .filter(visible)
        .map((el) => (el.innerText || el.textContent || "").trim().replace(/\s+/g, " "))
        .filter(Boolean)
        .slice(0, 8);
      return {
        title: document.title || location.pathname || location.href,
        url: location.href,
        headings,
        elements: elementFacts,
      };
    });

    pages.push({
      title: facts.title,
      url: facts.url,
      entry_path: targetUrl,
      structure_summary: summarizeStructure(facts),
      screenshot_path: relativeArtifact(screenshotFile),
      snapshot_path: relativeArtifact(snapshotFile),
    });
    for (const element of facts.elements) {
      elements.push({ ...element, page_url: facts.url });
    }

    for (const element of facts.elements) {
      if (queued.length + visited.size >= maxPages || actionCount >= maxActions) {
        break;
      }
      const href = sameOriginHref(element.href, start);
      if (!href || visited.has(normalizeUrl(href)) || queued.includes(href)) {
        continue;
      }
      if (isForbidden(`${element.name} ${href}`)) {
        blockers.push({
          page_ref: facts.url,
          reason_type: "forbidden_path",
          reason: `命中禁止路径，已跳过：${element.name || href}`,
          suggested_action: "如需覆盖该功能，请在安全测试环境中调整禁止路径后重新探索。",
        });
        continue;
      }
      queued.push(href);
      actionCount += 1;
    }

    for (const element of facts.elements) {
      if (queued.length + visited.size >= maxPages || actionCount >= maxActions) {
        break;
      }
      if (element.href || (element.type !== "button" && !(element.type === "input" && ["button", "submit"].includes(element.inputType)))) {
        continue;
      }
      if (isForbidden(`${element.name} ${element.locator}`)) {
        blockers.push({
          page_ref: facts.url,
          reason_type: "forbidden_path",
          reason: `命中禁止路径，已跳过：${element.name || element.locator}`,
          suggested_action: "如需覆盖该功能，请在安全测试环境中调整禁止路径后重新探索。",
        });
        continue;
      }
      const beforeUrl = page.url();
      try {
        const locator = page.locator("a,button,input,textarea,select,[role='button'],[role='link']").nth(element.index);
        await locator.click({ timeout: 2000 });
        actionCount += 1;
        await page.waitForLoadState("domcontentloaded", { timeout: navigationTimeout }).catch(() => {});
        const afterUrl = page.url();
        const href = sameOriginHref(afterUrl, start);
        if (href && normalizeUrl(href) !== normalizeUrl(beforeUrl) && !visited.has(normalizeUrl(href)) && !queued.includes(href)) {
          queued.push(href);
        }
      } catch (error) {
        blockers.push({
          page_ref: facts.url,
          reason_type: "interaction_failed",
          reason: `点击失败：${element.name || element.locator}。${String(error?.message || error).slice(0, 300)}`,
          suggested_action: "检查元素是否需要前置数据、权限、登录态或人工确认。",
        });
      } finally {
        if (page.url() !== facts.url) {
          await page.goto(facts.url, { waitUntil: "domcontentloaded" }).catch(() => {});
        }
      }
    }
  }

  const summary = `已探索 ${pages.length} 个页面，识别 ${elements.length} 个可交互元素，记录 ${blockers.length} 个阻塞项。`;
  console.log(JSON.stringify({
    status: pages.length > 0 ? (blockers.length > 0 ? "partial" : "completed") : "blocked",
    summary,
    pages,
    elements,
    blockers,
    action_count: actionCount,
    field_count: elements.filter((item) => ["input", "textarea", "select"].includes(item.type)).length,
    state_transition_count: Math.max(0, pages.length - 1),
  }));
} finally {
  await browser.close();
}

function normalizeUrl(value) {
  const url = new URL(value);
  url.hash = "";
  return url.href;
}

function sameOriginHref(value, start) {
  if (!value) return "";
  const url = new URL(value, start.href);
  if (!["http:", "https:"].includes(url.protocol)) return "";
  if (url.origin !== start.origin) return "";
  url.hash = "";
  return url.href;
}

function summarizeStructure(facts) {
  const headings = facts.headings.length ? `标题：${facts.headings.join(" / ")}。` : "";
  const counts = facts.elements.reduce((acc, item) => {
    acc[item.type] = (acc[item.type] || 0) + 1;
    return acc;
  }, {});
  const countText = Object.entries(counts).map(([type, count]) => `${type} ${count}`).join("、") || "未识别可交互元素";
  return `${headings}可交互元素：${countText}。`;
}

function relativeArtifact(filePath) {
  return path.relative(artifactRoot, filePath).replaceAll(path.sep, "/");
}

function isForbidden(value) {
  const normalized = String(value || "").toLowerCase();
  return forbiddenTerms.some((term) => term && normalized.includes(term));
}
