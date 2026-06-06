import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx", import.meta.url),
  "utf8",
);

test("requirement detail exposes the new requirement analysis tab contract", () => {
  assert.match(pageSource, /<TabsTrigger value="analysis">需求分析<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="preliminary">初步需求<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="pending">待确认问题<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, />需求澄清</);
});

test("review action is presented as requirement analysis", () => {
  assert.match(pageSource, /toast\.success\("需求分析已完成"\)/);
  assert.match(pageSource, /reviewLoading \? "分析中" : "需求分析"/);
  assert.match(pageSource, /setActiveTab\("analysis"\)/);
});

test("legacy query tabs route into requirement analysis", () => {
  assert.match(pageSource, /queryTab === "initial"[\s\S]*setActiveTab\("analysis"\)/);
  assert.match(pageSource, /queryTab === "clarification"[\s\S]*setActiveTab\("analysis"\)/);
});
