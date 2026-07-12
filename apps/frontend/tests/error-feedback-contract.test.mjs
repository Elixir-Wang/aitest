import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const errorFeedbackSource = readFileSync(new URL("../src/lib/error-feedback.ts", import.meta.url), "utf8");
const sonnerSource = readFileSync(new URL("../src/components/ui/sonner.tsx", import.meta.url), "utf8");

test("error feedback uses a normal error toast without a detail action", () => {
  assert.match(errorFeedbackSource, /toast\.error\(title,\s*\{/);
  assert.match(errorFeedbackSource, /void submitClientErrorLog\(item\)/);
  assert.doesNotMatch(errorFeedbackSource, /action:\s*\{/);
  assert.doesNotMatch(errorFeedbackSource, /label:\s*"查看详情"/);
  assert.doesNotMatch(errorFeedbackSource, /window\.location\.assign/);
});

test("error feedback toast stays selectable and does not override the global duration", () => {
  assert.doesNotMatch(errorFeedbackSource, /duration:\s*Infinity/);
  assert.doesNotMatch(errorFeedbackSource, /dismissible:\s*false/);
  assert.doesNotMatch(errorFeedbackSource, /cancel:\s*\{/);
  assert.doesNotMatch(errorFeedbackSource, /label:\s*"复制"/);
  assert.doesNotMatch(errorFeedbackSource, /navigator\.clipboard\.writeText/);
});

test("global sonner toast uses variant card styling and disables swipe gestures", () => {
  assert.match(sonnerSource, /closeButton/);
  assert.match(sonnerSource, /duration=\{5000\}/);
  assert.match(sonnerSource, /swipeDirections=\{\[\]\}/);
  assert.match(sonnerSource, /toast:\s*"cn-toast select-text rounded-xl border pr-16 shadow-md"/);
  assert.match(
    sonnerSource,
    /closeButton:\s*"!right-3 !left-auto !top-1\/2 !size-9 !-translate-y-1\/2 !\[transform:none\] !rounded-md .*after:content-\['关闭'\].*\[&>svg\]:hidden/,
  );
  assert.match(sonnerSource, /default:\s*"bg-card border-border text-foreground"/);
  assert.match(sonnerSource, /success:\s*"bg-card border-green-600\/50 text-foreground"/);
  assert.match(sonnerSource, /error:\s*"bg-card border-destructive\/50 text-foreground"/);
  assert.match(sonnerSource, /warning:\s*"bg-card border-amber-600\/50 text-foreground"/);
  assert.match(sonnerSource, /title:\s*"select-text text-xs font-medium leading-none"/);
  assert.match(sonnerSource, /description:\s*"select-text text-xs text-muted-foreground"/);
});
