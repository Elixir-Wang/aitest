import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/agents/page.tsx", import.meta.url), "utf8");

test("silicon employees page shows a dismissible integration notice", () => {
  assert.match(pageSource, /use client/);
  assert.match(pageSource, /Dialog open=\{open\} onOpenChange=\{setOpen\}/);
  assert.match(pageSource, /功能接入中/);
  assert.match(pageSource, /硅基员工即将上线/);
  assert.match(pageSource, /关闭提示后可预览硅基员工界面/);
  assert.match(pageSource, /SiliconOfficeDashboard embedded/);
});
