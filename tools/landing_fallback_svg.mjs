// Writes the landing page's no-WebGL sketch from the same plan as the 3D city:
//   node tools/landing_fallback_svg.mjs
import { writeFileSync } from 'node:fs';
import { buildPlan } from '../core/static/js/landing/plan.js';

const OUT = new URL('../core/static/img/landing/city_blueprint.svg', import.meta.url);
const W = 1400;
const H = 900;
const AZ = 0.7;
const TILT = 0.52;
const SCALE = 1.5;

const project = (x, y, z) => {
    const rx = x * Math.cos(AZ) - z * Math.sin(AZ);
    const rz = x * Math.sin(AZ) + z * Math.cos(AZ);
    return [Math.round(W / 2 + rx * SCALE), Math.round(H / 2 + 30 + (rz * TILT - y) * SCALE)];
};

// Whole pixels and relative moves, skipping what rounds to nothing, to keep the file small.
const { blueprint } = buildPlan();
let d = '';
let [cx, cy] = [0, 0];
for (let i = 0; i < blueprint.length; i += 6) {
    const [x0, y0] = project(blueprint[i], blueprint[i + 1], blueprint[i + 2]);
    const [x1, y1] = project(blueprint[i + 3], blueprint[i + 4], blueprint[i + 5]);
    if (x0 === x1 && y0 === y1) continue;
    if (x0 !== cx || y0 !== cy) d += `m${x0 - cx} ${y0 - cy}`;
    d += `l${x1 - x0} ${y1 - y0}`;
    [cx, cy] = [x1, y1];
}
writeFileSync(OUT, `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}"><path d="${d}" fill="none" stroke="#7fb6cb" stroke-width=".7"/></svg>\n`);
console.log(`${d.length} bytes of path data`);
