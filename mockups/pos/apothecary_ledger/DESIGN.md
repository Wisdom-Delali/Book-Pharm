---
name: Apothecary Ledger
colors:
  surface: '#fbf9f5'
  surface-dim: '#dbdad6'
  surface-bright: '#fbf9f5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3ef'
  surface-container: '#efeeea'
  surface-container-high: '#eae8e4'
  surface-container-highest: '#e4e2de'
  on-surface: '#1b1c1a'
  on-surface-variant: '#564241'
  inverse-surface: '#30312e'
  inverse-on-surface: '#f2f0ed'
  outline: '#897170'
  outline-variant: '#dcc0bf'
  surface-tint: '#a13c3f'
  primary: '#410007'
  on-primary: '#ffffff'
  primary-container: '#630d16'
  on-primary-container: '#eb7475'
  inverse-primary: '#ffb3b1'
  secondary: '#705a49'
  on-secondary: '#ffffff'
  secondary-container: '#f8dac5'
  on-secondary-container: '#755e4d'
  tertiary: '#271900'
  on-tertiary: '#ffffff'
  tertiary-container: '#412d00'
  on-tertiary-container: '#b7934d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdad8'
  primary-fixed-dim: '#ffb3b1'
  on-primary-fixed: '#410007'
  on-primary-fixed-variant: '#82252a'
  secondary-fixed: '#fbddc7'
  secondary-fixed-dim: '#dec1ac'
  on-secondary-fixed: '#28180b'
  on-secondary-fixed-variant: '#574333'
  tertiary-fixed: '#ffdea5'
  tertiary-fixed-dim: '#e9c176'
  on-tertiary-fixed: '#261900'
  on-tertiary-fixed-variant: '#5d4201'
  background: '#fbf9f5'
  on-background: '#1b1c1a'
  surface-variant: '#e4e2de'
typography:
  display-lg:
    fontFamily: Libre Caslon Text
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
  headline-lg:
    fontFamily: Libre Caslon Text
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-md:
    fontFamily: Libre Caslon Text
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-lg:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Hanken Grotesk
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  container-margin: 24px
  gutter: 16px
---

## Brand & Style

The design system is crafted for a desktop-first POS environment that bridges the gap between a classical study and a modern apothecary. The brand personality is scholarly, dependable, and meticulously organized. It evokes the tactile satisfaction of heavy paper stock and polished wood while maintaining the operational speed required for high-volume retail.

The visual style is **Corporate Modern with a Tactile twist**. It utilizes clean, high-density layouts to manage complex inventory data, softened by organic radius values and a warm, low-fatigue color palette. The aesthetic prioritizes legibility and functional elegance, ensuring that the interface feels like a professional tool rather than a generic digital surface.

## Colors

The palette is rooted in natural, traditional materials. 
- **Primary Burgundy (#630D16):** Reserved for high-priority actions (e.g., "Complete Sale," "Checkout") and active state indicators.
- **Secondary Wood-Brown (#4A3728):** Used for structural text, iconography, and secondary navigation elements to provide a grounded, professional feel.
- **Accent Gold (#C5A059):** Utilized sparingly for highlights, notifications, or specific data points that require visual distinction without the urgency of red.
- **Foundation Cream/Ivory:** The background is a layered combination of `#FDFBF7` (base) and `#F7F3ED` (containers), reducing eye strain during long shifts compared to pure white.

## Typography

This design system employs a classic pairing to balance heritage with utility. **Libre Caslon Text** is used for headings and branding elements, providing an authoritative, literary character. 

**Hanken Grotesk** serves as the primary workhorse for UI labels, inventory lists, and inputs. Its clean, geometric construction ensures maximum readability in high-density data grids. For numerical data such as SKU numbers or prices, **JetBrains Mono** is used to ensure tabular alignment and clear character distinction.

## Layout & Spacing

The layout follows a **Fixed-Fluid hybrid grid**. The main navigation is a fixed-width sidebar (240px), while the content area uses a 12-column fluid grid that adapts to desktop resolutions. 

A strict 4px baseline grid ensures vertical rhythm. High-density data tables use 8px (sm) cell padding to maximize information density without sacrificing touch/click targets for the mouse. Margins between major UI cards are set at 24px (lg) to create clear breathing room between functional modules (e.g., Product Catalog vs. Current Basket).

## Elevation & Depth

Hierarchy is established through **Tonal Layering** supplemented by **Ambient Shadows**. 

- **Level 0 (Base):** The Cream (#FDFBF7) background.
- **Level 1 (Cards):** Ivory (#F7F3ED) surfaces with a subtle 1px border (#E5DED3).
- **Level 2 (Active/Floating):** Use of extra-diffused shadows (e.g., `box-shadow: 0 4px 12px rgba(74, 55, 40, 0.08)`) to lift active modals or selected item cards.
- **Level 3 (Popovers):** Deeply diffused shadows with a slight Wood-Brown tint to maintain warmth in the depth effect.

Avoid heavy blacks in shadows; use tinted neutrals to keep the apothecary aesthetic cohesive.

## Shapes

The shape language is defined by a consistent 12px (0.75rem) radius for primary containers and cards. This softens the high-density layout, making the software feel approachable. 

Buttons and input fields utilize a slightly smaller 8px radius to maintain a sense of precision. Interactive elements like "Delete" or "Remove" may use sharper corners to subtly signal a change in intent, while decorative accents use fully circular (pill) caps.

## Components

### Buttons
- **Primary:** Burgundy (#630D16) background with White text. Bold weight.
- **Secondary:** Wood-Brown (#4A3728) outlines with a transparent background.
- **Ghost:** No background, Secondary text color, used for low-priority utility actions.

### Input Fields
- Background: Base Neutral (#FDFBF7).
- Border: 1.5px solid Wood-Brown at 20% opacity.
- Focus State: 1.5px solid Gold (#C5A059) with a subtle inner glow.

### Cards & Chips
- Product cards feature the 12px corner radius and contain the item price in the top-right using the Gold accent.
- Chips (Status/Category): Pill-shaped with a background 10% tint of the category color and 100% opacity text.

### Data Tables
- Row Height: 48px for standard, 40px for high-density mode.
- Header: Wood-Brown background with Cream text to create a strong visual anchor for columns.

### Icons
- Thin-stroke (1.5px) professional icons. 
- Color: Always Secondary Wood-Brown unless signifying an error (Burgundy) or warning (Gold).