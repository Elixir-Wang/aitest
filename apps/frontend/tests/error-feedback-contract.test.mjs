import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const errorFeedbackSource = readFileSync(new URL("../src/lib/error-feedback.ts", import.meta.url), "utf8");
const sonnerSource = readFileSync(new URL("../src/components/ui/sonner.tsx", import.meta.url), "utf8");

test("error feedback detail action opens the operation log detail page when a log id exists", () => {
  assert.match(
    errorFeedbackSource,
    /window\.location\.assign\(operationLogUrl\(result\?\.log_id, result\?\.trace_id \|\| traceId\)\)/,
  );
  assert.match(errorFeedbackSource, /return `\/settings\/logs\/\$\{encodeURIComponent\(logId\)\}`/);
  assert.match(errorFeedbackSource, /return operationLogListUrl\(keyword\)/);
});

test("error feedback toast stays selectable instead of adding a copy button", () => {
  assert.match(errorFeedbackSource, /duration:\s*Infinity/);
  assert.doesNotMatch(errorFeedbackSource, /dismissible:\s*false/);
  assert.doesNotMatch(errorFeedbackSource, /cancel:\s*\{/);
  assert.doesNotMatch(errorFeedbackSource, /label:\s*"复制"/);
  assert.doesNotMatch(errorFeedbackSource, /navigator\.clipboard\.writeText/);
});

test("global sonner toast uses variant card styling and disables swipe gestures", () => {
  assert.match(sonnerSource, /closeButton/);
  assert.match(sonnerSource, /swipeDirections=\{\[\]\}/);
  assert.match(sonnerSource, /toast:\s*"cn-toast select-text rounded-xl border pr-12 shadow-md"/);
  assert.match(sonnerSource, /closeButton:\s*"!right-3 !left-auto !top-1\/2 !-translate-y-1\/2 size-7 rounded-md/);
  assert.match(sonnerSource, /default:\s*"bg-card border-border text-foreground"/);
  assert.match(sonnerSource, /success:\s*"bg-card border-green-600\/50 text-foreground"/);
  assert.match(sonnerSource, /error:\s*"bg-card border-destructive\/50 text-foreground"/);
  assert.match(sonnerSource, /warning:\s*"bg-card border-amber-600\/50 text-foreground"/);
  assert.match(sonnerSource, /title:\s*"select-text text-xs font-medium leading-none"/);
  assert.match(sonnerSource, /description:\s*"select-text text-xs text-muted-foreground"/);
});
