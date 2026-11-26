// ============================================================
// FacilityIcons.js — one round badge icon per builtup.Facility type (map symbols + legend).
// Style: mainMap/styles/layerStyles.py ('builtup.Facility') picks 'facility-<category>' per feature.
// Layers.js awaits registerFacilityIcons() before it adds a layer whose symbol layout uses them;
// addCategoricalLegend() shows the same badge through facilityIconUrl().
// Categories mirror builtup/calculations/chain.py::CATEGORIES (+ the generic 'transportNode').
// ============================================================

(function () {
  'use strict';

  const PREFIX = 'facility-';
  const SIZE = 40;          // badge size in CSS px; rendered at RATIO x for sharp symbols
  const RATIO = 2;

  // glyphs on a 24 x 24 grid, white on the badge colour (BG marks a cut-out in the badge colour)
  const W = '#fff';
  const GLYPHS = {
    school: `<path fill="${W}" d="M12 5 2.5 10 12 15l7-3.7V16h2v-6zM6 13.4v3.6l6 3 6-3v-3.6l-6 3.2z"/>`,
    hospital: `<path fill="${W}" d="M10 4h4v6h6v4h-6v6h-4v-6H4v-4h6z"/>`,
    fire_station: `<path fill="${W}" d="M12 2.5c.8 3.4 5.5 5.6 5.5 10.8a5.5 5.5 0 0 1-11 0c0-2.2 1-3.6 2.3-4.8.1 1.9.9 3 2 3.4-.7-3 .1-6.600 1.200-9.400z"/>`,
    police_station: `<path fill="${W}" d="M12 3 19 6v5.500c0 4.600-3 7.600-7 9.500-4-1.900-7-4.900-7-9.500V6z"/><path fill="BG" d="m12 7.500 1.200 2.600 2.800.3-2.100 1.900.6 2.800-2.500-1.400-2.500 1.400.6-2.800L8 10.400l2.800-.3z"/>`,
    market: `<path fill="${W}" d="M5 9h14l1 11H4z"/><path fill="none" stroke="${W}" stroke-width="2" d="M8.500 9V7.500a3.500 3.500 0 0 1 7 0V9"/>`,
    shop: `<path fill="${W}" d="M5 9h14l1 11H4z"/><path fill="none" stroke="${W}" stroke-width="2" d="M8.500 9V7.500a3.500 3.500 0 0 1 7 0V9"/>`,
    supermarket: `<path fill="${W}" d="M2.500 4H6l.7 3H21l-2.200 7.500H8.800zM9.500 16.500a1.800 1.800 0 1 0 0 3.600 1.800 1.800 0 0 0 0-3.600zm8 0a1.800 1.800 0 1 0 0 3.600 1.800 1.800 0 0 0 0-3.600z"/>`,
    pharmacy: `<rect x="2.500" y="8.500" width="19" height="7" rx="3.500" fill="${W}" transform="rotate(-45 12 12)"/><path stroke="BG" stroke-width="1.800" d="m12 8.300 3.700 3.700"/>`,
    clinic_gp: `<path fill="${W}" d="M12 20.500S4.500 16 4.500 10.200A4.200 4.200 0 0 1 12 7.700a4.200 4.200 0 0 1 7.500 2.500C19.500 16 12 20.500 12 20.500z"/>`,
    childcare: `<circle cx="12" cy="7" r="3.200" fill="${W}"/><path fill="${W}" d="M5.500 21v-5.500a6.500 6.500 0 0 1 13 0V21z"/>`,
    library: `<path fill="${W}" d="M3 5h7.500a1.500 1.500 0 0 1 1.500 1.500V20a3 3 0 0 0-3-2H3zM21 5h-7.500A1.500 1.500 0 0 0 12 6.500V20a3 3 0 0 1 3-2h6z"/>`,
    sport: `<circle cx="12" cy="12" r="8" fill="none" stroke="${W}" stroke-width="2"/><path fill="none" stroke="${W}" stroke-width="1.800" d="M12 4v16M4 12h16M6.300 6.300c3 3 3 8.100 0 11.400M17.700 6.300c-3 3-3 8.100 0 11.400"/>`,
    bus_stop: `<path fill="${W}" d="M6 3.500h12A2 2 0 0 1 20 5.500V16h-1.500v2.500h-2.500V16H8v2.500H5.500V16H4V5.500a2 2 0 0 1 2-2z"/><path fill="BG" d="M6 6.500v4h12v-4z"/><circle cx="7.800" cy="13.300" r="1.200" fill="BG"/><circle cx="16.200" cy="13.300" r="1.200" fill="BG"/>`,
    tram_metro_stop: `<path fill="${W}" d="M7 2.500h10a2 2 0 0 1 2 2V16a3 3 0 0 1-3 3l1.500 2.500h-2L14.300 19H9.700L8.500 21.500h-2L8 19a3 3 0 0 1-3-3V4.500a2 2 0 0 1 2-2z"/><path fill="BG" d="M7 6v4.500h10V6z"/><circle cx="8.500" cy="14" r="1.300" fill="BG"/><circle cx="15.500" cy="14" r="1.300" fill="BG"/>`,
    train_station: `<path fill="${W}" d="M6 3h12a2 2 0 0 1 2 2v10a3 3 0 0 1-3 3l2 3h-2.500l-1.500-2.500H9.500L8 21H5.500l2-3a3 3 0 0 1-3.500-3V5a2 2 0 0 1 2-2z"/><path fill="BG" d="M6.500 6.500V11h11V6.500z"/><circle cx="8.500" cy="14.500" r="1.300" fill="BG"/><circle cx="15.500" cy="14.500" r="1.300" fill="BG"/>`,
  };
  // generic public-transport node (type transportNode without a known subtype) reuses the bus glyph
  GLYPHS.transportNode = GLYPHS.bus_stop;

  const COLORS = {
    school: '#1e88e5', hospital: '#e53935', fire_station: '#e64a19', police_station: '#3949ab',
    market: '#fb8c00', shop: '#fb8c00', supermarket: '#43a047', pharmacy: '#00acc1',
    clinic_gp: '#d81b60', childcare: '#f9a825', library: '#6d4c41', sport: '#689f38',
    bus_stop: '#00897b', tram_metro_stop: '#8e24aa', train_station: '#5e35b1', transportNode: '#00897b',
  };

  // Legend order: the facility types of builtup.models.Facility.TYPES grouped by theme.
  const LEGEND_ORDER = [
    ['school', 'School'], ['childcare', 'Childcare'], ['library', 'Library'], ['sport', 'Sport facility'],
    ['hospital', 'Hospital'], ['clinic_gp', 'Clinic / GP'], ['pharmacy', 'Pharmacy'],
    ['supermarket', 'Supermarket'], ['shop', 'Shop / market'],
    ['bus_stop', 'Bus stop'], ['tram_metro_stop', 'Tram / metro stop'], ['train_station', 'Train station'],
    ['fire_station', 'Fire station'], ['police_station', 'Police station'],
  ];

  function svg(category) {
    const color = COLORS[category] || '#757575';
    const glyph = (GLYPHS[category] || GLYPHS.hospital).replace(/BG/g, color);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 ${SIZE} ${SIZE}">` +
      `<circle cx="20" cy="20" r="18" fill="${color}" stroke="#ffffff" stroke-width="2.500"/>` +
      `<g transform="translate(8 8)">${glyph}</g></svg>`;
  }

  const urls = {};
  function facilityIconUrl(category) {
    return (urls[category] = urls[category] || 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg(category)));
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = url;
    });
  }

  /** Add every facility badge to the map (idempotent, also after a basemap style switch). */
  async function registerFacilityIcons() {
    if (typeof map === 'undefined' || !map) return;
    await Promise.all(Object.keys(GLYPHS).map(async (category) => {
      const id = PREFIX + category;
      if (map.hasImage(id)) return;
      const img = await loadImage(facilityIconUrl(category));
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = SIZE * RATIO;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      if (!map.hasImage(id)) {
        map.addImage(id, ctx.getImageData(0, 0, canvas.width, canvas.height), { pixelRatio: RATIO });
      }
    }));
  }

  /** Legend rows for the Facility layer: {label, icon} with the badge as data URL. */
  function facilityLegend() {
    return LEGEND_ORDER.map(([category, label]) => ({ label, color: COLORS[category], icon: facilityIconUrl(category) }));
  }

  window.registerFacilityIcons = registerFacilityIcons;
  window.facilityIconUrl = facilityIconUrl;
  window.facilityLegend = facilityLegend;
})();
