## Design System: URBAN PLANNING / CIVIC CARTOGRAPHY
     MINIMAL MAP DASHBOARD

     ### Pattern
     - **Name:** Minimal Single Column
     - **Conversion Focus:** Single CTA focus. Large typography.
     Lots of whitespace. No nav clutter. Mobile-first.
     - **CTA Placement:** Center, large CTA button
     - **Color Strategy:** Minimalist: Ink neutrals + one civic
     accent per role. Buttons: High contrast 7:1+. Text: Off-white/Dark grey
     - **Sections:** 1. Hero headline, 2. Short description, 3.
     Benefit bullets (3 max), 4. CTA, 5. Footer

     ### Style
     - **Name:** Civic Cartography Dashboard
     - **Mode Support:** Light ✓ Full | Dark ✓ Full
     - **Keywords:** Zoning-map palette, hairline rules, flat
     fills, technical/drafting labels, grid layout, restrained motion,
     maximum data legibility
     - **Best For:** Urban planning dashboards, infrastructure/
     utility monitoring, municipal reporting, land-use and cadastral
     tools, civic data platforms
     - **Performance:** ⚡ Excellent | **Accessibility:** ✓ WCAG
     AA

     ### Colors
     | Role | Hex | CSS Variable |
     |------|-----|--------------|
     | Background | `#080808` | `--color-background` |
     | Surface / Panel | `#111111` | `--color-primary` |
     | Surface Raised | `#1a1a1a` | `--color-secondary` |
     | On Surface | `#f0f0f0` | `--color-on-primary` |
     | Accent — Blueprint Cyanotype | `#1F4E5F` (UI tint `#2E6478`) | `--color-accent` |
     | Accent 2 — Zoning Brick | `#B5674A` | `--color-accent-2` |
     | Accent 3 — Survey Ochre | `#C99A3E` | `--color-accent-3` |
     | Border | `rgba(255,255,255,0.08)` | `--color-border` |
     | Success (OK) | `#22C55E` | `--color-success` |
     | Warning | `#F59E0B` | `--color-warning` |
     | Destructive/Bad | `#EF4444` | `--color-destructive` |

     *Notes: Dark ink background, one cool civic-blue accent (drawn
     from architectural blueprint/cyanotype paper) plus two warm
     zoning-map tones for categorical accents. Status colors
     (ok/warn/bad) stay semantic traffic-light hues, used flat —
     never as a glow.*

     ### Typography
     - **Heading:** Archivo
     - **Body:** Inter
     - **Mono (data / coordinates / units):** IBM Plex Mono
     - **Mood:** municipal, cartographic, drafting-table, surveyor,
     technical, restrained, civic infrastructure
     - **Best For:** Planning department dashboards, utility and
     infrastructure monitors, cadastral/GIS tools, government data
     portals
     - **Google Fonts:** https://fonts.google.com/share?selection.
     family=Inter:wght@400;500;600;700|IBM+Plex+Mono:wght@400;500
     |Archivo:wght@500;600;700
     - **CSS Import:**
     ```css
     @import url('https://fonts.googleapis.com/css2?family=Inter:w
     ght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family
     =Archivo:wght@500;600;700&display=swap');
     ```

     ### Key Effects
     Hover border-color change only (no lift, no glow), instant
     filter toggles, flat threshold zones on sliders, tabular-numeral
     alignment for data columns

     ### Avoid (Anti-patterns)
     - Ornate design
     - No filtering
     - Blurry / soft-focus shadows
     - Glossy gradients or shine bars (the `linear-gradient(90deg,
     transparent, accent, transparent)` "shimmer" look)
     - Glow / bloom `box-shadow` halos around active elements
     - Hover-lift (`translateY`) on cards — reads as generic SaaS,
     not a technical instrument panel
     - Neon or oversaturated accent colors

     ### Pre-Delivery Checklist
     - [ ] No emojis as icons (use SVG: Heroicons/Lucide)
     - [ ] cursor-pointer on all clickable elements
     - [ ] Hover states are flat (border/color only, 150-300ms,
     no shadow bloom or transform)
     - [ ] Light mode: text contrast 4.5:1 minimum
     - [ ] Focus states visible for keyboard nav
     - [ ] prefers-reduced-motion respected
     - [ ] Responsive: 375px, 768px, 1024px, 1440px
