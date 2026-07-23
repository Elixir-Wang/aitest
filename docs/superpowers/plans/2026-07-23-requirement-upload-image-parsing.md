# Requirement Upload Image Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a front-end-only image parsing option above the requirement file uploader, with “否” selected and “是” disabled as unsupported.

**Architecture:** Extend the existing requirement upload form with a controlled static `RadioGroup`. Reuse the page's current radio components and styling without adding state, request fields, validation, or backend behavior.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS, Radix-based `RadioGroup`, Biome.

## Global Constraints

- The feature is display-only in the frontend.
- “否” is always selected.
- “是” is disabled and displays “暂不支持”.
- No upload request, form validation, or backend API changes.
- Do not create a commit unless the user explicitly requests one.

---

### Task 1: Add Static Image Parsing Options

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/requirement-upload-page.tsx:312`

**Interfaces:**
- Consumes: Existing `Field`, `FieldLabel`, `Label`, `RadioGroup`, and `RadioGroupItem` components.
- Produces: A display-only image parsing field with no exported API or request payload changes.

- [ ] **Step 1: Add the static field before the uploader**

Insert this JSX immediately before the existing “上传文件” block:

```tsx
<Field>
  <FieldLabel>图片解析</FieldLabel>
  <RadioGroup className="grid gap-2 sm:grid-cols-2" value="no">
    <Label className="flex cursor-default items-center gap-3 rounded-lg border p-3 text-sm">
      <RadioGroupItem value="no" />
      否
    </Label>
    <Label className="text-muted-foreground flex cursor-not-allowed items-center gap-3 rounded-lg border p-3 text-sm">
      <RadioGroupItem disabled value="yes" />
      <span>是</span>
      <span className="rounded bg-muted px-2 py-0.5 text-xs">暂不支持</span>
    </Label>
  </RadioGroup>
</Field>
```

- [ ] **Step 2: Run focused static validation**

Run: `npm run check -- src/components/ai-testing/requirement-upload-page.tsx`

Expected: The modified component passes Biome checks without errors.

- [ ] **Step 3: Run the frontend build**

Run: `npm run build`

Expected: Next.js completes the production build successfully.

- [ ] **Step 4: Verify behavior in the browser**

Open the requirement upload page and confirm:

- “图片解析” appears immediately above “上传文件”.
- “否” is selected.
- “是” cannot be selected.
- “暂不支持” is visible next to “是”.
- Submitting a requirement sends the same request fields as before.
