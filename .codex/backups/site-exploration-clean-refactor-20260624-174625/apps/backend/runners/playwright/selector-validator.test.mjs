import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { verifySelectorCandidate } from "./selector-validator.mjs";

function locator(count, visible) {
  return {
    async count() {
      return count;
    },
    first() {
      return {
        async isVisible() {
          return visible;
        },
      };
    },
  };
}

function fakePage(overrides = {}) {
  return {
    getByRole: (role, options) => overrides.role?.(role, options) ?? locator(1, true),
    getByLabel: (text) => overrides.label?.(text) ?? locator(1, true),
    getByTestId: (text) => overrides.testid?.(text) ?? locator(1, true),
    getByText: (text) => overrides.text?.(text) ?? locator(1, true),
    locator: (text) => overrides.css?.(text) ?? locator(1, true),
  };
}

describe("verifySelectorCandidate", () => {
  it("records unique and visible selectors as verified", async () => {
    const verified = await verifySelectorCandidate(
      fakePage(),
      {
        kind: "role",
        role: "button",
        name: "保存",
        code: "page.getByRole('button', { name: '保存' })",
      },
    );

    assert.deepEqual(verified.verification, {
      checked: true,
      unique: true,
      visible: true,
      match_count: 1,
    });
  });

  it("records non-unique selectors without claiming visibility", async () => {
    const verified = await verifySelectorCandidate(
      fakePage({
        text: () => locator(2, true),
      }),
      {
        kind: "text",
        text: "保存",
        code: "page.getByText('保存')",
      },
    );

    assert.deepEqual(verified.verification, {
      checked: true,
      unique: false,
      visible: false,
      match_count: 2,
    });
  });
});
