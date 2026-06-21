import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const selectSource = readFileSync(new URL("../src/components/ui/animated-select-1.tsx", import.meta.url), "utf8");

test("animated select flattens mapped option arrays before injecting selection handlers", () => {
  assert.match(selectSource, /Children,\s*\n\s*type ComponentPropsWithoutRef/);
  assert.match(selectSource, /const childrenArray = Children\.toArray\(children\)/);
  assert.match(selectSource, /const childrenWithProps = childrenArray\.map/);
  assert.doesNotMatch(selectSource, /Array\.isArray\(children\) \? children : \[children\]/);
});
