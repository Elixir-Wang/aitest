import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  normalizeUrl,
  selectorUsable,
  slugify,
  stableElementId,
} from "./page-facts.mjs";

describe("page facts shared helpers", () => {
  it("normalizes urls without hashes and trailing non-root slashes", () => {
    assert.equal(normalizeUrl("https://example.test/path/#section"), "https://example.test/path");
    assert.equal(normalizeUrl("https://example.test/"), "https://example.test/");
    assert.equal(normalizeUrl("not a url"), "not a url");
    assert.equal(normalizeUrl(undefined, { invalidFallback: "raw" }), undefined);
  });

  it("builds stable readable element ids", () => {
    assert.equal(stableElementId({ role: "button", name: "创建 智能体" }, 3), "button-创建-智能体-003");
    assert.equal(stableElementId({ action_type: "fill", text: "Search" }, 12), "fill-search-012");
  });

  it("keeps selector usability rules in one place", () => {
    assert.equal(selectorUsable({ verification: { checked: true, unique: true, visible: true } }), true);
    assert.equal(selectorUsable({ verification: { checked: true, unique: true, visible: false } }), false);
  });

  it("slugifies empty and punctuation-only labels to element", () => {
    assert.equal(slugify(""), "element");
    assert.equal(slugify("..."), "element");
  });
});
