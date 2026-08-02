import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("api client redirects authenticated pages to login when backend rejects an expired session", () => {
  assert.match(apiClientSource, /function isAuthRequiredError\(error: ApiRequestError\)/);
  assert.match(apiClientSource, /error\.status === 401 && error\.code === "AUTH_REQUIRED"/);
  assert.match(apiClientSource, /function redirectToLoginAfterAuthExpired\(\)/);
  assert.match(apiClientSource, /useAuthStore\.getState\(\)\.logout\(\);/);
  assert.match(
    apiClientSource,
    /window\.location\.assign\(`\/auth\/v1\/login\?next=\$\{encodeURIComponent\(`\$\{pathname\}\$\{search\}`\)\}`\);/,
  );
});

test("api client does not redirect while already on an auth page", () => {
  assert.match(apiClientSource, /if \(pathname\.startsWith\("\/auth\/"\)\) {\s*return;\s*}/);
});

test("all api request helpers use the shared unauthorized response handling", () => {
  const throwApiErrorCalls = apiClientSource.match(/throwApiError\(response, payload\);/g) ?? [];
  assert.equal(throwApiErrorCalls.length, 3);
  assert.match(apiClientSource, /function throwApiError\(response: Response, payload: unknown\): never/);
  assert.match(apiClientSource, /if \(isAuthRequiredError\(error\)\) {\s*redirectToLoginAfterAuthExpired\(\);\s*}/);
});

test("api request handles successful empty responses without reading data from null payload", () => {
  assert.match(apiClientSource, /if \(response\.status === 204 \|\| payload === null\) {\s*return undefined as T;\s*}/);
});
