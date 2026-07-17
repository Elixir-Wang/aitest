import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const appRoot = fileURLToPath(new URL("../src/app/(main)", import.meta.url));

function collectPageFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      return collectPageFiles(path);
    }
    return entry.name === "page.tsx" ? [path] : [];
  });
}

test("application routes do not handwrite breadcrumb arrays", () => {
  const handwrittenPages = collectPageFiles(appRoot).filter((path) =>
    /breadcrumbs\s*=\s*\{\s*\[/.test(readFileSync(path, "utf8")),
  );

  assert.deepEqual(handwrittenPages, []);
});
