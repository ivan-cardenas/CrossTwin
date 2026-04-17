## Design System: GEOSPATIAL DIGITAL TWIN DARK PRECISION        
     MINIMAL MAP DASHBOARD                                           
                                                                       
     ### Pattern                                                       
     - **Name:** Minimal Single Column                                 
     - **Conversion Focus:** Single CTA focus. Large typography.
     Lots of whitespace. No nav clutter. Mobile-first.                 
     - **CTA Placement:** Center, large CTA button                     
     - **Color Strategy:** Minimalist: Brand + white #FFFFFF +         
     accent. Buttons: High contrast 7:1+. Text: Black/Dark grey        
     - **Sections:** 1. Hero headline, 2. Short description, 3.        
     Benefit bullets (3 max), 4. CTA, 5. Footer                        
                                                                       
     ### Style                                                         
     - **Name:** Data-Dense Dashboard                                  
     - **Mode Support:** Light ✓ Full | Dark ✓ Full                    
     - **Keywords:** Multiple charts/widgets, data tables, KPI         
     cards, minimal padding, grid layout, space-efficient, maximum     
      data visibility                                                  
     - **Best For:** Business intelligence dashboards, financial       
     analytics, enterprise reporting, operational dashboards, data
      warehousing                                                      
     - **Performance:** ⚡ Excellent | **Accessibility:** ✓ WCAG       
     AA

     ### Colors
     | Role | Hex | CSS Variable |
     |------|-----|--------------|
     | Primary | `#0F172A` | `--color-primary` |
     | On Primary | `#FFFFFF` | `--color-on-primary` |
     | Secondary | `#1E293B` | `--color-secondary` |
     | Accent/CTA | `#22C55E` | `--color-accent` |
     | Background | `#020617` | `--color-background` |
     | Foreground | `#F8FAFC` | `--color-foreground` |
     | Muted | `#1A1E2F` | `--color-muted` |
     | Border | `#334155` | `--color-border` |
     | Destructive | `#EF4444` | `--color-destructive` |
     | Ring | `#0F172A` | `--color-ring` |

     *Notes: Dark bg + green positive indicators*

     ### Typography
     - **Heading:** Space Grotesk
     - **Body:** Inter
     - **Mood:** web3, bitcoin, defi, digital gold, fintech,
     crypto, trustless, luminescent, precision, dark
     - **Best For:** DeFi protocols and wallets, NFT platforms,
     metaverse social apps, high-tech brand landing pages
     - **Google Fonts:** https://fonts.google.com/share?selection.
     family=Inter:wght@400;500;600;700|JetBrains+Mono:wght@400;500
     |Space+Grotesk:wght@500;600;700
     - **CSS Import:**
     ```css
     @import url('https://fonts.googleapis.com/css2?family=Inter:w
     ght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family
     =Space+Grotesk:wght@500;600;700&display=swap');
     ```

     ### Key Effects
     Hover tooltips, chart zoom on click, row highlighting on
     hover, smooth filter animations, data loading spinners

     ### Avoid (Anti-patterns)
     - Ornate design
     - No filtering

     ### Pre-Delivery Checklist
     - [ ] No emojis as icons (use SVG: Heroicons/Lucide)
     - [ ] cursor-pointer on all clickable elements
     - [ ] Hover states with smooth transitions (150-300ms)
     - [ ] Light mode: text contrast 4.5:1 minimum
     - [ ] Focus states visible for keyboard nav
     - [ ] prefers-reduced-motion respected
     - [ ] Responsive: 375px, 768px, 1024px, 1440px