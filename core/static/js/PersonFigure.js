// PersonFigure.js — the interactive male / female figure of the Thermal Comfort
// person panel (SolweigTool.js). Pure drawing: PersonFigure.render(container, state)
// builds an SVG from the person (sex, posture, height, weight, age, activity,
// garments); the caller handles clicks on `[data-region]` (Tops, Legs, Feet,
// Underwear) and keeps the form fields as the source of truth.
//
// Limbs are drawn as thick round-capped lines between joints, so a garment is the
// same line, wider, over part of the limb; legs and arms swing while walking.
(function () {
  'use strict';

  const GROUND = 262;          // y of the soles (viewBox units)
  const FIGURE_H = 248;        // drawn height of the figure at scale 1
  const STAGE_M = 2.2;         // the stage spans the tallest accepted person (m)
  const REF_HEIGHT_M = 1.75;   // Höppe (1999) PET reference person
  const REF_BMI = 22.9;        // 75 kg / 1.75 m², the reference person
  const SKIN = '#cfae93';
  const HAIR = '#4a3a30';
  const HAIR_GREY = '#b9b9b9';

  const BODY = {
    male:   { sh: 27, waist: 19, hip: 15, head: 14, arm: 8.5, thigh: 15, shin: 11.5 },
    female: { sh: 23, waist: 15, hip: 19, head: 13, arm: 7.5, thigh: 15.5, shin: 10.5 },
  };

  // Garment colours, listed inner → outer so later ones are drawn over earlier ones.
  const COLOUR = {
    briefs: '#9aa3ad', bra: '#c87aa0', t_shirt: '#e8e8e8',
    sleeveless_blouse: '#e6a8c4', short_sleeve_shirt: '#5aa0d8', long_sleeve_shirt: '#4a86c0',
    sweatshirt: '#8a8f98',
    short_shorts: '#d8a24a', walking_shorts: '#c9b27a', trousers_thin: '#6b7c93', trousers_thick: '#3f4c63',
    skirt_thin: '#c27a9a', skirt_thick: '#8d4f70',
    dress_sleeveless: '#d8607a', dress_short_sleeve: '#e07a5a',
    sweater_thin: '#7a5aa8', sweater_thick: '#5d3f8a', jacket_thin: '#4f7d5a', jacket_thick: '#2f5a3e',
    down_jacket: '#d8b33a', coat: '#7a4a30', parka: '#3d4a2f',
    ankle_socks: '#f0f0f0', calf_socks: '#e0e0e0', sandals: '#c9a060', shoes: '#2a2a2a', boots: '#4a2f1f',
  };
  const ORDER = Object.keys(COLOUR);

  // Torso garments: [top y, bottom y, grow (half-width, units), flare (per unit below the hips)].
  const TORSO = {
    briefs: [120, 134, 0.8, 0], bra: [70, 80, 0.6, 0],
    t_shirt: [56, 114, 1.5, 0], sleeveless_blouse: [56, 110, 1.5, 0],
    short_sleeve_shirt: [56, 118, 1.5, 0], long_sleeve_shirt: [56, 122, 1.5, 0], sweatshirt: [56, 126, 2.5, 0],
    skirt_thin: [112, 172, 1.5, 0.4], skirt_thick: [112, 184, 1.5, 0.4],
    dress_sleeveless: [56, 176, 1.5, 0.35], dress_short_sleeve: [56, 176, 1.5, 0.35],
    sweater_thin: [56, 128, 3, 0], sweater_thick: [56, 132, 4.5, 0],
    jacket_thin: [56, 140, 5.5, 0], jacket_thick: [56, 140, 6.5, 0], down_jacket: [56, 144, 8, 0],
    coat: [56, 196, 6, 0.12], parka: [56, 204, 7, 0.14],
  };
  // Sleeves: [from, to] along the arm (0 = shoulder, 1 = elbow, 2 = hand), padding.
  const SLEEVE = {
    t_shirt: [0, 0.35, 2], short_sleeve_shirt: [0, 0.55, 2], dress_short_sleeve: [0, 0.55, 2],
    long_sleeve_shirt: [0, 1.9, 2], sweatshirt: [0, 1.9, 3],
    sweater_thin: [0, 1.9, 3.5], sweater_thick: [0, 1.9, 5],
    jacket_thin: [0, 1.95, 4.5], jacket_thick: [0, 1.95, 5.5], down_jacket: [0, 1.95, 7],
    coat: [0, 1.95, 5], parka: [0, 1.95, 6],
  };
  // Leg garments: [from, to] along the leg (0 = hip, 1 = knee, 2 = ankle), padding.
  const LEG = {
    short_shorts: [0, 0.45, 3], walking_shorts: [0, 0.85, 3],
    trousers_thin: [0, 1.97, 2.5], trousers_thick: [0, 1.97, 3.5],
    ankle_socks: [1.75, 2, 1.5], calf_socks: [1.35, 2, 1.5], boots: [1.5, 2, 3.5],
  };

  // Walking swing per activity: [amplitude deg, period s].
  const SWING = { walk_slow: [12, 0.9], walk: [18, 0.7], walk_fast: [26, 0.5] };

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const num = v => Math.round(v * 10) / 10;

  // Half-width of the torso at height y (shoulders → waist → hips), plus grow and flare below the hips.
  function halfWidth(b, y, grow, flare) {
    const prof = [[54, b.sh * 0.45], [60, b.sh], [104, b.waist], [132, b.hip]];
    let w;
    if (y <= prof[0][0]) w = prof[0][1];
    else if (y >= prof[3][0]) w = b.hip;
    else {
      let i = 0;
      while (y > prof[i + 1][0]) i++;
      const [y0, w0] = prof[i], [y1, w1] = prof[i + 1];
      w = w0 + (w1 - w0) * (y - y0) / (y1 - y0);
    }
    return w + grow + (y > 132 ? flare * (y - 132) : 0);
  }

  function torsoShape(b, y0, y1, grow, flare, fill, extra = '') {
    const left = [], right = [];
    for (let y = y0; y < y1; y += 6) {
      const w = halfWidth(b, y, grow, flare);
      left.push(`${num(70 - w)},${y}`);
      right.unshift(`${num(70 + w)},${y}`);
    }
    const w = halfWidth(b, y1, grow, flare);
    left.push(`${num(70 - w)},${y1}`);
    right.unshift(`${num(70 + w)},${y1}`);
    return `<polygon points="${left.concat(right).join(' ')}" fill="${fill}" stroke="${fill}" stroke-width="2" ` +
           `stroke-linejoin="round" ${extra}/>`;
  }

  // A limb is [p0, p1, p2] with per-bone widths; draws it from bone-coordinate a to b (0..2).
  function limb(pts, widths, a, b, colour, pad, extra = '') {
    let out = '';
    for (let i = 0; i < 2; i++) {
      const lo = Math.max(a, i), hi = Math.min(b, i + 1);
      if (hi <= lo) continue;
      const [p, q] = [pts[i], pts[i + 1]];
      const at = t => [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
      const [s, e] = [at(lo - i), at(hi - i)];
      out += `<line x1="${num(s[0])}" y1="${num(s[1])}" x2="${num(e[0])}" y2="${num(e[1])}" ` +
             `stroke="${colour}" stroke-width="${num(widths[i] + pad)}" stroke-linecap="round" ${extra}/>`;
    }
    return out;
  }

  function legGroup(b, side, sitting, garments, walkClass) {
    const x = 70 + side * 8;
    const pts = sitting
      ? [[x, 128], [70 + side * 13, 166], [70 + side * 13, 226]]
      : [[x, 128], [70 + side * 9, 196], [70 + side * 9, 254]];
    const widths = [b.thigh, b.shin];
    const ankle = pts[2];
    const toe = [ankle[0] + side * 8, ankle[1] + 4];
    let out = limb(pts, widths, 0, 2, SKIN, 0);
    out += `<line x1="${ankle[0]}" y1="${ankle[1]}" x2="${toe[0]}" y2="${toe[1]}" stroke="${SKIN}" ` +
           `stroke-width="7" stroke-linecap="round"/>`;
    ORDER.forEach(k => {
      if (!garments.has(k)) return;
      if (LEG[k]) out += limb(pts, widths, LEG[k][0], LEG[k][1], COLOUR[k], LEG[k][2]);
      if (k === 'shoes' || k === 'boots') {
        out += `<line x1="${ankle[0]}" y1="${ankle[1] - 1}" x2="${toe[0] + side}" y2="${toe[1]}" ` +
               `stroke="${COLOUR[k]}" stroke-width="${k === 'boots' ? 10 : 8.5}" stroke-linecap="round"/>`;
      } else if (k === 'sandals') {
        out += `<line x1="${ankle[0]}" y1="${ankle[1] + 2}" x2="${toe[0]}" y2="${toe[1] + 1}" ` +
               `stroke="${COLOUR[k]}" stroke-width="4" stroke-linecap="round"/>`;
      }
    });
    out += `<line class="pf-hit" data-region="Feet" x1="${ankle[0]}" y1="${ankle[1]}" x2="${toe[0]}" y2="${toe[1]}" ` +
           `stroke-width="13" stroke-linecap="round"><title>Footwear</title></line>`;
    out += limb(pts, [b.thigh + 3, b.shin + 3], 0, 1.7, 'transparent', 0, 'class="pf-hit" data-region="Legs"');
    return `<g class="pf-limb ${walkClass}" style="transform-origin:${x}px 128px">${out}</g>`;
  }

  function armGroup(b, side, sitting, garments, walkClass) {
    const sx = 70 + side * (b.sh - 2);
    const pts = sitting
      ? [[sx, 64], [70 + side * (b.sh + 1), 100], [70 + side * 17, 130]]
      : [[sx, 64], [70 + side * (b.sh + 3), 98], [70 + side * (b.sh + 3), 130]];
    const widths = [b.arm, b.arm - 1];
    const hand = pts[2];
    let out = limb(pts, widths, 0, 2, SKIN, 0);
    out += `<circle cx="${hand[0]}" cy="${hand[1]}" r="${num(b.arm * 0.62)}" fill="${SKIN}"/>`;
    ORDER.forEach(k => {
      if (garments.has(k) && SLEEVE[k]) out += limb(pts, widths, SLEEVE[k][0], SLEEVE[k][1], COLOUR[k], SLEEVE[k][2]);
    });
    out += limb(pts, [b.arm + 4, b.arm + 3], 0, 2, 'transparent', 0, 'class="pf-hit" data-region="Tops"');
    return `<g class="pf-limb ${walkClass}" style="transform-origin:${sx}px 64px">${out}</g>`;
  }

  function head(b, sex, grey) {
    const hair = grey ? HAIR_GREY : HAIR;
    const back = sex === 'female'
      ? `<ellipse cx="70" cy="33" rx="${b.head + 3.5}" ry="${b.head + 6}" fill="${hair}"/>`
      : '';
    const cap = sex === 'female'
      ? `<path d="M${70 - b.head},28 A${b.head},${b.head} 0 0 1 ${70 + b.head},28 Q70,${b.head - 2} ${70 - b.head},28Z" fill="${hair}"/>`
      : `<path d="M${70 - b.head},27 A${b.head},${b.head} 0 0 1 ${70 + b.head},27 Q70,17 ${70 - b.head},27Z" fill="${hair}"/>`;
    return `${back}<line x1="70" y1="42" x2="70" y2="56" stroke="${SKIN}" stroke-width="${b.sh > 25 ? 8 : 6.5}"/>` +
           `<circle cx="70" cy="28" r="${b.head}" fill="${SKIN}"/>${cap}`;
  }

  function ruler(heightM, sy) {
    const y = h => GROUND - h * (FIGURE_H / STAGE_M);
    let out = '<g class="pf-ruler">';
    [0.5, 1, 1.5, 2].forEach(m => {
      out += `<line x1="6" y1="${num(y(m))}" x2="12" y2="${num(y(m))}"/>` +
             `<text x="14" y="${num(y(m) + 3)}">${m}</text>`;
    });
    out += `<line class="pf-ruler-now" x1="4" y1="${num(y(heightM))}" x2="136" y2="${num(y(heightM))}"/>` +
           `<text class="pf-ruler-now-label" x="136" y="${num(y(heightM) - 3)}" text-anchor="end">${heightM.toFixed(2)} m</text>`;
    out += '</g>';
    return out;
  }

  /**
   * state: { sex, position, age, height, weight, activity, garments[], region }
   * Returns nothing; replaces the container's content with the figure.
   */
  function render(container, state) {
    const sex = state.sex === 'female' ? 'female' : 'male';
    const b = BODY[sex];
    const sitting = state.position === 'sitting';
    const garments = new Set(state.garments || []);
    const height = clamp(Number(state.height) || REF_HEIGHT_M, 1, 2.2);
    const weight = clamp(Number(state.weight) || 75, 20, 200);
    const sy = height / STAGE_M;
    const bmiFactor = clamp(Math.sqrt((weight / (height * height)) / REF_BMI), 0.8, 1.4);
    const sx = sy * bmiFactor;
    const swing = !sitting && SWING[state.activity];
    const walk = swing ? 'pf-walk' : '';
    const grey = Number(state.age) >= 65;

    // Legs (and the bench) first; the torso overlaps the hips; arms last so sleeves sit on top.
    let fig = '';
    if (sitting) {
      // In the shifted frame: the seat is just under the hips, the legs reach the ground (232 + 30).
      fig += '<g class="pf-bench"><rect x="22" y="138" width="96" height="8" rx="3"/>' +
             '<line x1="30" y1="146" x2="30" y2="232"/><line x1="110" y1="146" x2="110" y2="232"/></g>';
    }
    const figure = [];
    figure.push(legGroup(b, -1, sitting, garments, walk ? 'pf-a' : ''));
    figure.push(legGroup(b, 1, sitting, garments, walk ? 'pf-b' : ''));
    figure.push(head(b, sex, grey));
    figure.push(torsoShape(b, 54, 132, 0, 0, SKIN));
    ORDER.forEach(k => {
      if (garments.has(k) && TORSO[k]) {
        const [y0, y1, grow, flare] = TORSO[k];
        figure.push(torsoShape(b, y0, y1, grow, flare, COLOUR[k]));
      }
    });
    figure.push(armGroup(b, -1, sitting, garments, walk ? 'pf-b' : ''));
    figure.push(armGroup(b, 1, sitting, garments, walk ? 'pf-a' : ''));
    figure.push(torsoShape(b, 54, 118, 0, 0, 'transparent', 'class="pf-hit" data-region="Tops"'));
    figure.push(torsoShape(b, 118, 134, 1, 0, 'transparent', 'class="pf-hit" data-region="Underwear"'));
    fig += figure.join('');

    const shift = sitting ? 30 : 0;
    const transform = `translate(70 ${GROUND}) scale(${num(sx * 100) / 100} ${num(sy * 100) / 100}) translate(-70 ${-GROUND})`;
    const style = swing ? `--pf-amp:${swing[0]}deg;--pf-period:${swing[1]}s` : '';
    const label = `${sex} figure, ${height.toFixed(2)} m, ${weight} kg, ${sitting ? 'sitting' : 'standing'}`;
    container.innerHTML =
      `<svg class="pf-svg" viewBox="0 0 140 270" role="img" aria-label="${label}" style="${style}" ` +
      `data-active="${state.region || ''}">` +
      `<line class="pf-ground" x1="20" y1="${GROUND + 1}" x2="136" y2="${GROUND + 1}"/>` +
      ruler(height, sy) +
      `<g transform="${transform}"><g transform="translate(0 ${shift})">${fig}</g></g></svg>`;
  }

  window.PersonFigure = { render };
})();
