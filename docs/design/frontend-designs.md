# Frontend Design Studies

Milestone 10 provides ten selectable visual systems for the same safe query
workflow. The routes intentionally share behavior and API state but vary in
layout, typography, surface treatment, status presentation, and palette.

## Routes

| Route | Design | Direction |
| --- | --- | --- |
| `/1` | Swiss Analytical Desk | Editorial grid, rules, and red research signals |
| `/2` | Functional Brutalism | Raw blocks, visible structure, and direct labels |
| `/3` | Frosted Research Console | Restrained translucent layers and depth |
| `/4` | Clay Analytics Workspace | Tactile surfaces and pressed controls |
| `/5` | Archival Terminal | Amber workstation and session-record language |
| `/6` | Monochrome Data Atlas | High-contrast hierarchy without color dependence |
| `/7` | Desk Ledger | Paper, tabs, reports, and audit stamps |
| `/8` | Bento Schema Observatory | Deliberate tiles for query artifacts |
| `/9` | Art Deco Query Bureau | Geometric framing and restrained brass |
| `/10` | Cartographic Field Guide | Survey-sheet composition and schema terrain |

The root route `/` is a design gallery. The design selector inside every
workspace switches between routes without changing the product behavior.

## Shared Product Rules

- Review Mode is the default.
- Auto Mode remains subject to backend validation and resource limits.
- Edited SQL is visibly marked as untrusted and is sent to the backend for full
  revalidation.
- Frontend validation indicators never authorize execution.
- Results are rendered as text data, never as HTML.
- Query history is current-session only and stores no credentials.
- Database credentials, connection URLs, model keys, and database selection are
  backend-only.

## Research References

- [Brutalist Websites](https://brutalistwebsites.com/) informed the raw
  structural direction of Design 2.
- [IBM Carbon Design System](https://carbondesignsystem.com/) informed the
  treatment of enterprise controls, data states, and accessible interaction.
- [Nielsen Norman Group data-table guidance](https://www.nngroup.com/articles/data-tables/)
  informed table scanning, horizontal overflow, row comparison, and result
  state handling.

These references informed principles rather than copied layouts or assets.
