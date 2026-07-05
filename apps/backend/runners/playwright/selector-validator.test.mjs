import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { verifySelectorCandidate } from "./selector-validator.mjs";

function locator(count, visible) {
  return {
    filter() {
      return this;
    },
    getByRole() {
      return this;
    },
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

  it("verifies contextual role containers without XPath", async () => {
    const calls = [];
    const verified = await verifySelectorCandidate(
      fakePage({
        role: (role, options) => {
          calls.push(["role", role, options || null]);
          return locator(1, true);
        },
      }),
      {
        kind: "contextual",
        container: { kind: "role", role: "listitem", hasText: "测试_自主规划智能体" },
        target: { kind: "role", role: "button", name: "对话历史" },
        code: "page.getByRole('listitem').filter({ hasText: '测试_自主规划智能体' }).getByRole('button', { name: '对话历史' })",
      },
    );

    assert.deepEqual(verified.verification, {
      checked: true,
      unique: true,
      visible: true,
      match_count: 1,
    });
    assert.equal(calls[0][1], "listitem");
  });
});
