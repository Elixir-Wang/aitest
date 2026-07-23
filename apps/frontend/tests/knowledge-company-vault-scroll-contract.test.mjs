import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/knowledge/page.tsx", import.meta.url), "utf8");

test("company knowledge vault constrains long documents to an internal scroll container", () => {
  const vaultSource = pageSource.slice(pageSource.indexOf("function CompanyKnowledgeVault("));

  assert.match(vaultSource, /grid min-h-0 flex-1 overflow-hidden/);
  assert.match(vaultSource, /min-h-0 flex-1 overflow-hidden rounded-lg border bg-background/);
  assert.match(vaultSource, /<main className="h-full min-h-0 min-w-0 overflow-hidden">/);
  assert.match(vaultSource, /className="min-h-0 flex-1 overflow-auto p-4"/);
});
