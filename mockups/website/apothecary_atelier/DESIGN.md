---
name: Apothecary Atelier
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
  on-surface-variant: '#4d4635'
  inverse-surface: '#31312c'
  inverse-on-surface: '#f3f0ea'
  outline: '#7f7663'
  outline-variant: '#d0c5af'
  surface-tint: '#735c00'
  primary: '#735c00'
  on-primary: '#ffffff'
  primary-container: '#d4af37'
  on-primary-container: '#554300'
  inverse-primary: '#e9c349'
  secondary: '#af2b3e'
  on-secondary: '#ffffff'
  secondary-container: '#fd6673'
  on-secondary-container: '#680018'
  tertiary: '#77574d'
  on-tertiary: '#ffffff'
  tertiary-container: '#d2aa9e'
  on-tertiary-container: '#5b3e35'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffe088'
  primary-fixed-dim: '#e9c349'
  on-primary-fixed: '#241a00'
  on-primary-fixed-variant: '#574500'
  secondary-fixed: '#ffdada'
  secondary-fixed-dim: '#ffb3b5'
  on-secondary-fixed: '#40000b'
  on-secondary-fixed-variant: '#8e0f28'
  tertiary-fixed: '#ffdbd0'
  tertiary-fixed-dim: '#e7bdb1'
  on-tertiary-fixed: '#2c160e'
  on-tertiary-fixed-variant: '#5d4037'
  background: '#fcf9f2'
  on-background: '#1c1c18'
  surface-variant: '#e5e2db'
typography:
  display-lg:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-md:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
  price-tag:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '700'
    lineHeight: '1'
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  container-max: 1440px
  margin-desktop: 40px
  margin-mobile: 20px
  gutter: 24px
  card-padding: 24px
  section-gap: 64px
---

## Brand & Style

The design system embodies the essence of a modern literary apothecary—warm, intellectual, and curated. It targets a sophisticated audience that appreciates the tactile nature of reading but demands the fluidity of modern e-commerce.

The visual style is **Contemporary Minimalist with Tactile accents**. It leverages hyper-rounded corners (24px+) and soft, ambient shadows to create "floating" interface elements that feel physically approachable. A subtle dot pattern on the cream background provides a paper-like texture, reinforcing the literary theme without cluttering the airy whitespace. The emotional response should be one of calm, comfort, and premium discovery.

## Colors

This design system uses a warm, high-contrast palette inspired by classic library materials:
- **Ivory Cream (#FCF9F2):** The primary canvas color, used for backgrounds to reduce eye strain and provide a "paper" feel.
- **Warm Gold (#D4AF37):** Used exclusively for primary action buttons, price points, and high-priority highlights to drive conversion.
- **Deep Burgundy (#800020):** An accent color for secondary interactions, brand marks, and category highlights.
- **Wood Brown (#5D4037):** Used for iconography, subtle borders, and secondary typography.
- **Surface Texture:** The background should feature a subtle repeating dot grid using `surface_dot_pattern` at 16px intervals to evoke the feel of high-end stationery.

## Typography

The typography strategy balances the authority of a literary serif with the functional clarity of a modern sans-serif. 

**Playfair Display** is reserved for titles, book names, and section headings to provide a premium, editorial feel. **Inter** handles all functional UI, body copy, and metadata to ensure maximum legibility at small sizes. Labels and metadata should use uppercase Inter with slight letter-spacing to create a disciplined, "cataloged" aesthetic.

## Layout & Spacing

The layout follows a **Fluid Grid with Fixed Constraints**. It uses a 12-column system for desktop with wide 24px gutters to maintain the "airy" feel. 

- **Masonry Influence:** Drawing from the reference images, content cards (book previews, featured collections) use varying aspect ratios but align to the grid, creating a modern, asymmetric gallery feel.
- **Safe Zones:** Content is inset with generous 40px margins on desktop to prevent the UI from feeling cramped.
- **Reflow:** On mobile, the grid collapses to 2 columns for product cards and 1 column for feature hero sections, with horizontal scrolling "chip" filters for navigation.

## Elevation & Depth

This design system avoids harsh shadows in favor of **Ambient Tonal Layers**. 

Hierarchy is created through "Floating Surfaces":
1. **Level 0 (Base):** The Cream Ivory background with the subtle dot pattern.
2. **Level 1 (Cards):** Pure white (#FFFFFF) cards with a very soft, diffused shadow (0px 10px 30px rgba(93, 64, 55, 0.08)). These cards have large radii.
3. **Level 2 (Interaction):** Elements like active buttons or hovered cards increase their shadow spread slightly and may lift 2px via a Y-axis transform.

Floating navigation bars and bottom sheets use a high-blur backdrop filter (glassmorphism) to maintain context of the content underneath while providing a distinct layer for controls.

## Shapes

The shape language is defined by **hyper-rounded geometry**. 

Containers and cards must use a minimum radius of 24px. Buttons and interaction chips are fully pill-shaped (rounded-full). This softness contrasts with the formal Serif typography, making the e-commerce experience feel friendly and modern rather than stiff or academic. Product imagery should follow the same rounding rules to integrate seamlessly into the cards.

## Components

### Buttons
Primary buttons are pill-shaped, using the **Warm Gold** background with white text. Secondary buttons use a transparent background with a 1.5px **Wood Brown** border.

### Product Cards
Cards feature a pure white background, 24px corner radius, and a "floating" shadow. The price is always displayed in a pill-shaped Gold tag in the bottom right or top left of the card. Titles in Playfair Display, authors in Inter.

### Navigation Pills
The sidebar and top navigation use pill-shaped active states. The active item should have a **Deep Burgundy** background with white text, or a soft cream background if used as a toggle.

### Input Fields
Fields are oversized with 16px padding and 12px corner radius. Borders are light Wood Brown (20% opacity). Focus states use a 2px Deep Burgundy ring.

### Chips & Tags
Used for book genres or filters. Pill-shaped, small font size (label-md), with a soft background color derived from the primary/secondary palette at 10% opacity.