import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/tasks/page.tsx", import.meta.url), "utf8");

test("task list keeps long task names compact and reveals the full value on overflow", () => {
  assert.match(pageSource, /<Table className="min-w-\[980px\] table-fixed">/);
  assert.match(pageSource, /<TableHead className="w-\[34%\]">任务名称<\/TableHead>/);
  assert.match(pageSource, /function OverflowTooltipText\(\{ value \}: \{ value: string \}\)/);
  assert.match(pageSource, /className="block min-w-0 truncate"/);
  assert.match(pageSource, /scrollWidth > node\.clientWidth \+ 1/);
  assert.match(
    pageSource,
    /<TooltipContent className="max-w-md whitespace-normal break-words leading-5" side="top" sideOffset=\{6\}>/,
  );
  assert.match(pageSource, /<OverflowTooltipText value=\{task\.title\} \/>/);
});
