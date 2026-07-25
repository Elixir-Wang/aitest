import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const apiPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);

test("api client preserves browser multipart boundary and encodes debug files", () => {
  assert.match(apiClientSource, /options\.body instanceof FormData/);
  assert.match(apiClientSource, /formData\.append\("payload", JSON\.stringify\(payload\)\)/);
  assert.match(apiClientSource, /formData\.append\(`file::\$\{fieldName\}`/);
});

test("endpoint debug form keeps structured values and files separately", () => {
  assert.match(apiPageSource, /bodyValues: Record<string, string>/);
  assert.match(apiPageSource, /bodyFiles: Record<string, File \| null>/);
  assert.match(apiPageSource, /getRequestBodyFields\(activeEndpoint\.request_body\)/);
});

test("multipart request body renders schema fields and a binary file input", () => {
  assert.match(apiPageSource, /isStructuredRequestBody\(getRequestBodyContentType\(activeEndpoint\.request_body\)\)/);
  assert.match(apiPageSource, /type="file"/);
  assert.match(apiPageSource, /htmlFor=\{inputId\}/);
  assert.match(apiPageSource, /点击选择文件/);
  assert.match(apiPageSource, /field\.required/);
  assert.match(apiPageSource, /field\.description/);
});

test("debug request summary represents multipart data and file metadata", () => {
  assert.match(apiPageSource, /const contentType = String\(request\.content_type/);
  assert.match(apiPageSource, /requestArgs\.push\("data=payload"\)/);
  assert.match(apiPageSource, /requestArgs\.push\("files=files"\)/);
});
