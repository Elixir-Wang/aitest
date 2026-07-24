import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const createPageSource = readFileSync(
  new URL("../src/components/ai-testing/requirement-upload-page.tsx", import.meta.url),
  "utf8",
);
const detailPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx", import.meta.url),
  "utf8",
);
const uploadClientSource = readFileSync(new URL("../src/lib/requirement-upload-client.ts", import.meta.url), "utf8");

test("requirement create and append flows share the resumable upload client", () => {
  assert.match(createPageSource, /uploadRequirementFiles\(\{/);
  assert.match(detailPageSource, /uploadRequirementFiles\(\{/);
  assert.doesNotMatch(createPageSource, /new XMLHttpRequest\(\)/);
  assert.doesNotMatch(detailPageSource, /new XMLHttpRequest\(\)/);
});

test("requirement upload defaults stay at 20MB, 10 files, and concurrency 3", () => {
  assert.match(uploadClientSource, /max_file_size_bytes: 20 \* 1024 \* 1024/);
  assert.match(uploadClientSource, /max_files: 10/);
  assert.match(uploadClientSource, /concurrency: 3/);
  assert.match(
    uploadClientSource,
    /const workerCount = Math\.min\(Math\.max\(session\.concurrency, 1\), pending\.length\)/,
  );
});

test("upload progress uses the same stable file key as the file picker", () => {
  assert.match(uploadClientSource, /return `\$\{file\.name\}-\$\{file\.lastModified\}-\$\{file\.size\}`/);
  assert.match(createPageSource, /requirementUploadFileKey\(file\)/);
  assert.match(detailPageSource, /requirementUploadFileKey\(file\)/);
});
