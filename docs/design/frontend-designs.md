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
| `/library` | Internal component and token preview |

The former `/1` through `/9` design routes and the design-selection gallery have
been removed.

## Component Library

Reusable primitives live under `frontend/src/design-system`:

- `Panel`
- `SectionHeader`
- `Button`
- `StatusBadge`
- `Notice`
- `TagList`
- `CodeBlock`
- `EmptyState`

Foundation tokens live in `tokens.css`, reset behavior lives in `reset.css`,
and shared composition styles live in `globals.css`. Query-specific components
compose these primitives rather than defining private status or surface systems.

The `/library` route renders the same production primitives used by the query
workspace. It is the reference page for extending the system.

## Safety Rules

- Review Mode remains the default.
- Auto Mode remains subject to backend validation and resource limits.
- Edited SQL is visibly untrusted and is revalidated by FastAPI.
- Frontend validation indicators never authorize execution.
- Returned database values are rendered as text.
- Credentials and connection details remain backend-only.
