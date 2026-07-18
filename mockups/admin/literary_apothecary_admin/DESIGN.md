---
name: Literary Apothecary Admin
colors:
  surface: '#fcf9f2'
  surface-dim: '#dcdad3'
  surface-bright: '#fcf9f2'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3ec'
  surface-container: '#f0eee7'
  surface-container-high: '#ebe8e1'
  surface-container-highest: '#e5e2db'
  on-surface: '#1c1c18'
  on-surface-variant: '#584141'
  inverse-surface: '#31312c'
  inverse-on-surface: '#f3f0ea'
  outline: '#8c7071'
  outline-variant: '#e0bfbf'
  surface-tint: '#af2b3e'
  primary: '#570013'
  on-primary: '#ffffff'
  primary-container: '#800020'
  on-primary-container: '#ff828a'
  inverse-primary: '#ffb3b5'
  secondary: '#765749'
  on-secondary: '#ffffff'
  secondary-container: '#fed4c2'
  on-secondary-container: '#795a4c'
  tertiary: '#735c00'
  on-tertiary: '#ffffff'
  tertiary-container: '#cca730'
  on-tertiary-container: '#4f3d00'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdada'
  primary-fixed-dim: '#ffb3b5'
  on-primary-fixed: '#40000b'
  on-primary-fixed-variant: '#8e0f28'
  secondary-fixed: '#ffdbcc'
  secondary-fixed-dim: '#e6bead'
  on-secondary-fixed: '#2c160b'
  on-secondary-fixed-variant: '#5c4033'
  tertiary-fixed: '#ffe088'
  tertiary-fixed-dim: '#e9c349'
  on-tertiary-fixed: '#241a00'
  on-tertiary-fixed-variant: '#574500'
  background: '#fcf9f2'
  on-background: '#1c1c18'
  surface-variant: '#e5e2db'
typography:
  display-lg:
    fontFamily: EB Garamond
    fontSize: 48px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: EB Garamond
    fontSize: 32px
    fontWeight: '500'
    lineHeight: '1.3'
  headline-md:
    fontFamily: EB Garamond
    fontSize: 24px
    fontWeight: '500'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: EB Garamond
    fontSize: 28px
    fontWeight: '500'
    lineHeight: '1.3'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 260px
  gutter: 24px
  margin-page: 32px
  card-padding: 24px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

The design system is built for a "business back-office" environment that balances administrative density with a high-end, scholarly aesthetic. It targets internal stakeholders who manage complex inventories, combining the efficiency of a modern SaaS tool with the heritage feel of a premium bookstore or traditional apothecary.

The visual style is a blend of **Modern Corporate** and **Editorial Minimalism**. It utilizes a "contained" layout strategy where information is nested within soft, card-based structures to maintain order without feeling claustrophobic. The emotional response is one of calm authority, precision, and timelessness. 

Key stylistic pillars include:
- **Heritage Palette:** Warm, paper-like backgrounds paired with deep, academic accents.
- **Structured Airiness:** Ample white space (or cream space) between data-dense modules to prevent cognitive overload.
- **Tactile Softness:** Pill-shaped interactive elements and rounded containers that soften the "hard data" typical of admin portals.

## Colors

The palette is rooted in a warm, cream-based foundation to reduce eye strain during long-form data management. 

- **Primary (Burgundy):** Used for high-level navigation states, primary buttons, and critical branding elements.
- **Secondary (Wood-Brown):** Applied to secondary UI controls, sidebar icons, and grounding elements.
- **Tertiary (Gold):** Reserved specifically for "Key Performance Indicators" (KPIs), success states, and high-value call-to-actions.
- **Neutral (Cream/Ivory):** The primary background color, providing a softer alternative to pure white (#FFFFFF), which is reserved for the interior of data cards to create a subtle lift.

## Typography

This design system employs a dual-font strategy to balance character with utility.

- **Headlines (EB Garamond):** A sophisticated serif that provides an authoritative, literary feel. Use this for page titles, card headers, and significant data points (e.g., total revenue).
- **Interface & Data (Manrope):** A modern, highly legible sans-serif. Its geometric but warm construction ensures that complex tables, forms, and labels remain readable at small sizes. 

For data-heavy views, use `body-md` for table rows and `label-md` with slight letter-spacing for column headers to create clear visual separation.

## Layout & Spacing

The layout follows a **Fixed Sidebar + Fluid Grid** model. 

- **Sidebar:** A fixed-width navigation bar on the left. It uses a slightly darker tint of the cream background or a subtle wood-brown border to separate it from the main content.
- **Main Canvas:** A fluid area that houses a responsive card-based grid. Elements should snap to a 12-column system on desktop.
- **Rhythm:** A base-8 spacing system is used. 24px is the standard gutter between cards to maintain the "airy" feel while 16px is used for internal card padding to keep data dense.
- **Mobile Reflow:** On mobile devices, the sidebar collapses into a hamburger menu, and the multi-column card grid stacks vertically with 16px horizontal margins.

## Elevation & Depth

Visual hierarchy is achieved through **Tonal Layering** and **Ambient Shadows** rather than heavy lines.

- **Level 0 (Background):** The base Cream (#FCF9F2) layer.
- **Level 1 (Cards):** Pure White (#FFFFFF) surfaces with a very soft, diffused shadow (0px 4px 20px rgba(92, 64, 51, 0.06)). This "wood-tinted" shadow feels more natural and premium than a neutral grey.
- **Level 2 (Interactive/Floating):** Elements like dropdowns or active modals use a more pronounced shadow and a thin 1px border in #E5E1D8 to ensure separation from the card layer.
- **Active States:** Subtle inset shadows are used for pressed buttons to mimic physical "squishy" interaction.

## Shapes

The shape language is consistently rounded to evoke a modern, approachable feel.

- **Cards & Containers:** Use `rounded-lg` (1rem / 16px) for the primary containers.
- **Buttons & Inputs:** Use `rounded-md` (0.5rem / 8px) for standard interface elements.
- **Pills:** Navigation tabs and status badges (e.g., "Active", "Pending") must be fully rounded (pill-shaped) to distinguish them from functional buttons.
- **Sidebar Selection:** The active state in the sidebar navigation uses a "squircle" or pill-shaped highlight.

## Components

### Buttons & CTAs
- **Primary:** Burgundy background, white text. Pill-shaped or 8px rounded corners.
- **Secondary:** Transparent with a wood-brown border and text.
- **Highlight (Gold):** Used exclusively for high-impact actions like "Export Report" or "Finalize Order."

### Navigation Tabs
- Use the "Pill-style" seen in the reference image. The active tab should have a soft white background with a subtle shadow, while inactive tabs remain transparent or ghosted.

### Cards
- Standard cards feature a 1px border (#E5E1D8) and the soft wood-tinted shadow. 
- Header areas within cards should use `headline-md` in EB Garamond.

### Input Fields
- Inputs should have a subtle cream fill (#FCF9F2) to differentiate them from the white card surface. On focus, the border transitions to burgundy or wood-brown.

### Lists & Data Tables
- Use Manrope for all table data. Rows should be separated by thin, low-contrast lines. Hover states on rows should utilize a very faint cream highlight.

### Sidebar
- Icons should be minimal, utilizing the wood-brown color. The active menu item should be highlighted with a primary burgundy accent or a soft-filled pill shape.