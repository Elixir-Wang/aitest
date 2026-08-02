import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const versionPage = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/versions/page.tsx", import.meta.url),
  "utf8",
);
const uploadPage = readFileSync(
  new URL("../src/components/ai-testing/requirement-upload-page.tsx", import.meta.url),
  "utf8",
);
const requirementList = readFileSync(
  new URL("../src/components/ai-testing/requirements-page.tsx", import.meta.url),
  "utf8",
);
const requirementDetail = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx", import.meta.url),
  "utf8",
);
const uploadClient = readFileSync(new URL("../src/lib/requirement-upload-client.ts", import.meta.url), "utf8");

test("project versions are maintained inside a project", () => {
  assert.match(versionPage, /`\/projects\/\$\{projectId\}\/versions`/);
  assert.match(versionPage, /创建版本/);
  assert.match(versionPage, /设为当前版本/);
  assert.match(versionPage, /创建后设为当前版本/);
  assert.doesNotMatch(versionPage, /status|发布|归档/);
});

test("new requirements select and submit a project version", () => {
  assert.match(uploadPage, /所属版本/);
  assert.match(uploadPage, /versions\.find\(\(item\) => item\.is_default\)/);
  assert.match(uploadPage, /projectVersionId/);
  assert.match(uploadClient, /project_version_id: options\.mode === "new" \? options\.projectVersionId : ""/);
  assert.match(uploadClient, /projectVersionId: options\.mode === "new" \? options\.projectVersionId : ""/);
});

test("requirement list displays only the project version number", () => {
  assert.match(requirementList, /所属版本/);
  assert.match(requirementList, /item\.project_version\?\.version \?\? "-"/);
  assert.doesNotMatch(requirementList, /全部版本/);
  assert.doesNotMatch(requirementList, /item\.project_version\.name/);
});

test("requirement detail can reassign its project version", () => {
  assert.match(requirementDetail, /\/project-version/);
  assert.match(requirementDetail, /method: "PATCH"/);
  assert.match(requirementDetail, /需求所属版本已更新/);
});
