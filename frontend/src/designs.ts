export type Design = {
  id: string;
  name: string;
  category: string;
  description: string;
  className: string;
  signature: string;
};

export const designs: Design[] = [
  {
    id: "1",
    name: "Swiss Analytical Desk",
    category: "Editorial",
    description: "A precise research instrument built from rules, type, and red signals.",
    className: "design-swiss",
    signature: "QUERY INSTRUMENT",
  },
  {
    id: "2",
    name: "Functional Brutalism",
    category: "Brutalist",
    description: "Raw edges, visible structure, and direct language for serious review.",
    className: "design-brutal",
    signature: "READ ONLY / REVIEW REQUIRED",
  },
  {
    id: "3",
    name: "Frosted Research Console",
    category: "Glassmorphism",
    description: "Quiet translucent layers for a calm view into a complex workflow.",
    className: "design-glass",
    signature: "SCHEMA CONTEXT",
  },
  {
    id: "4",
    name: "Clay Analytics Workspace",
    category: "Claymorphism",
    description: "A tactile workspace where controls feel placed, pressed, and considered.",
    className: "design-clay",
    signature: "WORKFLOW TOKEN",
  },
  {
    id: "5",
    name: "Archival Terminal",
    category: "Retro UI",
    description: "A restrained amber workstation for questions, audits, and result reports.",
    className: "design-terminal",
    signature: "SESSION RECORD",
  },
  {
    id: "6",
    name: "Monochrome Data Atlas",
    category: "Monochromatic",
    description: "A high-contrast atlas where hierarchy never depends on color alone.",
    className: "design-mono",
    signature: "POLICY LEDGER",
  },
  {
    id: "7",
    name: "Desk Ledger",
    category: "Skeuomorphic",
    description: "An analyst's paper desk with tabs, reports, stamps, and readable evidence.",
    className: "design-ledger",
    signature: "BACKEND AUDIT",
  },
  {
    id: "8",
    name: "Bento Schema Observatory",
    category: "Bento Grid",
    description: "A tile-based observatory that gives each query artifact a deliberate place.",
    className: "design-bento",
    signature: "RELATIONSHIP MAP",
  },
  {
    id: "9",
    name: "Art Deco Query Bureau",
    category: "Art Deco",
    description: "Geometric framing and restrained brass for a formal query bureau.",
    className: "design-deco",
    signature: "QUERY SEAL",
  },
  {
    id: "10",
    name: "Cartographic Field Guide",
    category: "Naturalist",
    description: "A field guide for navigating schema terrain and grounded results.",
    className: "design-map",
    signature: "SCHEMA TERRAIN",
  },
];

export function getDesign(id: string): Design {
  return designs.find((design) => design.id === id) ?? designs[0];
}
