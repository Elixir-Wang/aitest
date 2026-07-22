# API Asset Location Badges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move API field location badges from every field row to the corresponding section heading to reduce visual crowding.

**Architecture:** Keep the existing API detail component and data model unchanged. Derive unique section locations from each section's existing `ApiFieldRow[]`, render them beside the heading, remove the location cell from `FieldRow`, and add the fixed response location badge beside the response heading.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS, existing shadcn `Badge` component, Biome.

## Global Constraints

- Only change the API asset detail presentation layer.
- Do not alter OpenAPI parsing or the `ApiFieldRow` data structure.
- Keep status code and Content-Type controls on the right side of section headings.
- Show only parameter locations that exist in the section rows.
- Preserve responsive wrapping and existing visual tokens.

---

### Task 1: Promote field locations to headings

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx:2942`

**Interfaces:**
- Consumes: Existing `ApiFieldRow[]` values and each row's `location` property.
- Produces: Section-level location badges and a four-column `FieldRow` layout without repeated location badges.

- [ ] **Step 1: Record the current verification baseline**

Run: `rtk npm run check -- src/app/(main)/projects/[projectId]/automation/api/page.tsx`

Expected: The existing file is checked before modification; unrelated existing diagnostics, if any, are recorded rather than fixed.

- [ ] **Step 2: Derive and render section location badges**

Inside `EndpointFieldSection`, derive locations while preserving row order:

```tsx
const locations = Array.from(new Set(rows.map((row) => row.location)));
```

Render the title and locations as one wrapping group, while leaving Content-Type on the right:

```tsx
<div className="flex flex-wrap items-center gap-2">
  <h3 className="font-semibold text-lg">{title}</h3>
  {locations.map((location) => (
    <Badge className="w-fit font-normal" key={location} variant="secondary">
      {location}
    </Badge>
  ))}
</div>
```

- [ ] **Step 3: Remove the repeated field location column**

Change `FieldRow` to a four-column desktop grid and delete the `row.location` badge cell:

```tsx
<div className="grid gap-3 py-3 md:grid-cols-[minmax(220px,1.1fr)_64px_56px_minmax(220px,1.4fr)] md:items-center md:gap-2">
```

- [ ] **Step 4: Add the response location badge**

Wrap the response title and a fixed `response` badge in a left-side title group:

```tsx
<div className="flex flex-wrap items-center gap-2">
  <h3 className="font-semibold text-lg">响应信息</h3>
  <Badge className="w-fit font-normal" variant="secondary">
    response
  </Badge>
</div>
```

- [ ] **Step 5: Run focused static verification**

Run: `rtk npm run check -- src/app/(main)/projects/[projectId]/automation/api/page.tsx`

Expected: Exit code 0 with no diagnostics for the modified file.

- [ ] **Step 6: Verify the rendered API asset detail**

Open the local frontend API asset page and confirm:

- `header`, `path`, `query`, and `body` appear only beside their section headings.
- `response` appears beside `响应信息`.
- Field rows retain name, type, required state, description, examples, and constraints.
- Status selection and Content-Type remain on the heading's right side.
- Narrow viewport wrapping does not overflow.
