---
name: playwright_cli
display_name: Playwright CLI
description: Automate browser interactions, test web pages and work with Playwright tests.
enabled: true
allowed-tools: Bash(playwright-cli:*) Bash(npx:*) Bash(npm:*)
---

# Browser Automation with playwright-cli

This skill is adapted from the installed `.agents/skills/playwright-cli` skill for the site exploration agent. All real browser actions must come from Playwright CLI. 所有真实浏览器动作必须来自 Playwright CLI。Do not infer pages, fields, buttons, states, or locators without CLI evidence.

## Quick Start

```bash
playwright-cli open
playwright-cli goto https://playwright.dev
playwright-cli snapshot
playwright-cli click e15
playwright-cli type "page.click"
playwright-cli press Enter
playwright-cli screenshot
playwright-cli close
```

If the global command is unavailable, try the local version:

```bash
npx --no-install playwright-cli --version
```

When the local version is available, use `npx playwright-cli` in commands. Otherwise install the CLI before exploration:

```bash
npm install -g @playwright/cli@latest
```

## Core Commands

```bash
playwright-cli open
playwright-cli open https://example.com/
playwright-cli goto https://playwright.dev
playwright-cli snapshot
playwright-cli click e3
playwright-cli dblclick e7
playwright-cli fill e5 "user@example.com" --submit
playwright-cli type "search query"
playwright-cli press Enter
playwright-cli hover e4
playwright-cli select e9 "option-value"
playwright-cli check e12
playwright-cli uncheck e12
playwright-cli go-back
playwright-cli go-forward
playwright-cli reload
playwright-cli close
```

## Evidence Capture

Use snapshots as the primary exploration artifact. Screenshots, traces, request logs, console logs, and generated locators are supporting evidence.

```bash
playwright-cli snapshot
playwright-cli snapshot --filename=after-click.yaml
playwright-cli snapshot --depth=4
playwright-cli snapshot --boxes
playwright-cli screenshot --filename=page.png
playwright-cli tracing-start
playwright-cli tracing-stop
playwright-cli console
playwright-cli requests
playwright-cli generate-locator e5 --raw
```

Every page fact must reference at least one evidence source:

- Page URL.
- Page title.
- Snapshot path.
- Screenshot path.
- Trace path.
- DOM, accessibility, console, or request summary collected through Playwright CLI.

Every locator must include the source page and a stability judgment.

## Targeting Elements

Prefer refs from `playwright-cli snapshot` for actions during exploration:

```bash
playwright-cli snapshot
playwright-cli click e15
```

CSS selectors and Playwright locators are allowed when refs are insufficient:

```bash
playwright-cli click "#main > button.submit"
playwright-cli click "getByRole('button', { name: 'Submit' })"
playwright-cli click "getByTestId('submit-button')"
```

Use semantic locators where possible. Prefer role, label, placeholder, text with stable scope, and test id over brittle CSS paths.

## Browser Sessions

Use named sessions for isolated workflows and clean them up when done:

```bash
playwright-cli -s=site-exploration open https://example.com --persistent
playwright-cli -s=site-exploration snapshot
playwright-cli -s=site-exploration close
playwright-cli close-all
```

Storage state can be saved and loaded when login state is intentionally reused:

```bash
playwright-cli state-save auth.json
playwright-cli state-load auth.json
playwright-cli cookie-list
playwright-cli localstorage-list
playwright-cli sessionstorage-list
```

## Advanced Inspection

Use `eval` and `run-code` only when normal CLI commands cannot capture the needed fact.

```bash
playwright-cli eval "document.title"
playwright-cli eval "el => el.textContent" e5
playwright-cli eval "el => el.getAttribute('data-testid')" e5
playwright-cli run-code "async page => await page.waitForLoadState('networkidle')"
playwright-cli run-code "async page => page.url()"
```

`run-code` must be a single function expression. Do not use import, export, or require syntax inside it.

## Safety Rules

- Do not click destructive, payment, external delivery, bulk notification, production release, or irreversible paths.
- Do not write passwords, tokens, verification codes, cookies, or secrets into logs, Markdown, JSON, screenshots, or trace summaries.
- Do not turn exploration facts into formal business requirements.
- Do not claim a module is explored unless the relevant browser evidence exists.
- If Playwright CLI is unavailable, blocked by authentication, blocked by captcha, or unable to reach the site, record a blocker instead of guessing.

## Output Discipline

For site exploration, summarize only facts observed through Playwright CLI. When a fact is uncertain, label it as uncertain and include the missing evidence or next action.
