import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { extname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const errorFeedbackSource = readFileSync(new URL("../src/lib/error-feedback.ts", import.meta.url), "utf8");
const persistentToastSource = readFileSync(new URL("../src/lib/toast.ts", import.meta.url), "utf8");
const sonnerSource = readFileSync(new URL("../src/components/ui/sonner.tsx", import.meta.url), "utf8");

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return [".ts", ".tsx"].includes(extname(entry.name)) ? [path] : [];
  });
}

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

test("all application error toasts use the persistent system-log wrapper", () => {
  assert.match(persistentToastSource, /void persistDisplayedError\(message, options\)/);
  assert.match(persistentToastSource, /sonnerToast\.error\(message, options\)/);

  const rawSonnerErrorImports = sourceFiles(fileURLToPath(new URL("../src", import.meta.url)))
    .filter((path) => !path.endsWith(join("lib", "error-feedback.ts")))
    .filter((path) => !path.endsWith(join("lib", "toast.ts")))
    .filter((path) => /import\s+\{\s*toast\s*\}\s+from\s+["']sonner["']/.test(readFileSync(path, "utf8")))
    .filter((path) => /toast\.error\s*\(/.test(readFileSync(path, "utf8")));

  assert.deepEqual(rawSonnerErrorImports, []);
});

test("global sonner toast uses variant card styling and disables swipe gestures", () => {
  assert.doesNotMatch(sonnerSource, /from "next-themes"/);
  assert.match(sonnerSource, /usePreferencesStore\(\(state\) => \(state\.themeMode === "dark" \? "dark" : "light"\)\)/);
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
  assert.match(sonnerSource, /description:\s*"select-text text-xs !text-muted-foreground"/);
});
