import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const previewSource = readFileSync(
  new URL("../src/components/ai-testing/markdown-preview.tsx", import.meta.url),
  "utf8",
);
const knowledgePageSource = readFileSync(new URL("../src/app/(main)/knowledge/page.tsx", import.meta.url), "utf8");

test("markdown preview hides machine metadata before rendering", () => {
  assert.match(previewSource, /prepareMarkdownForPreview\(content\)/);
  assert.match(previewSource, /replace\(\/\^---/);
  assert.match(previewSource, /replace\(\/<!--\[\\s\\S\]\*\?-->/);
});

test("rejected case knowledge uses its restrained reading style", () => {
  assert.match(knowledgePageSource, /rejected-test-case-library/);
  assert.match(knowledgePageSource, /rejected-case-markdown/);
});
