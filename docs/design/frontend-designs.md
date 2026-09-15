# Frontend Design System

The production interface uses one visual language: the **Cartographic Field
Guide**. The design treats a query as an analyst's expedition through source
schema, backend policy, SQL evidence, and returned data.

## Visual Language

- Map cream canvas: `#EEE7D7`.
- Warm report surface: `#F8F3E8`.
- Ink blue text: `#243C4A`.
- Moss for successful or grounded states: `#4C6651`.
- Clay for primary action and important signals: `#B86C50`.
- Ochre for warnings and field notes: `#C4A35A`.
- Fog for recessed controls and metadata: `#D5D8CE`.

Typography combines the Design 1 type system with the Design 10 field-guide
composition:

- `Space Grotesk` for page titles and section headings.
- `DM Sans` for controls, body copy, labels, and explanations.
- `DM Mono` for SQL, query IDs, hashes, and technical metadata.

The interface uses restrained dashed survey borders, report sheets, route-like
workflow markers, and field-note callouts. Decorative map language never
pretends to be a complete database schema or replaces the actual backend data.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Canonical production workspace |
| `/10` | Replaced with `/` for the former Design 10 URL |

The former `/1` through `/9` design routes and the design-selection gallery have
been removed.

## Component Library

Reusable Tailwind-based primitives live under `frontend/src/design-system`:

- `Panel`
- `SectionHeader`
- `Button`
- `StatusBadge`
- `Notice`
- `TagList`
- `CodeBlock`
- `EmptyState`

Tailwind is loaded through the Vite plugin in `frontend/vite.config.ts`. Theme
tokens live in `tokens.css` as Tailwind `@theme` values, and feature components
compose utility classes rather than defining private CSS selectors. There is no
public component-library route; this Markdown document is the reference for
extending the system.

Use the following rules when extending the interface:

- Prefer existing theme utilities such as `bg-canvas`, `text-ink`, `border-border`,
  and `font-display`.
- Keep layout, responsive behavior, focus states, and status styling in JSX
  utility classes.
- Add a new token to `tokens.css` before introducing a repeated arbitrary value.
- Keep production components free of custom stylesheet selectors.
- Preserve the distinction between moss success, clay action, ochre warning, and
  danger failure states.
- Keep the production workspace focused on the question, session history, and
  backend-provided evidence; avoid persistent explanatory rails and redundant
  footer copy.
- Keep execution-mode controls compact, equal in size, and content-sized on
  desktop while allowing them to expand to the available width on mobile.

## Safety Rules

- Review Mode remains the default.
- Auto Mode remains subject to backend validation and resource limits.
- Edited SQL is visibly untrusted and is revalidated by FastAPI.
- Frontend validation indicators never authorize execution.
- Returned database values are rendered as text.
- Credentials and connection details remain backend-only.
