# Vendored front-end libraries (landing page)

The repo has no JS build step, so these files are committed as they are. Versions are pinned by folder name.

- `three-0.187.0/three.module.min.js`: npm `three@0.187.0`. The package no longer ships a minified
  build, so this is `build/three.module.js` minified once:
  `npx esbuild@0.25.10 build/three.module.js --bundle --minify --format=esm --legal-comments=none --outfile=three.module.min.js`
- `gsap-3.15.0/gsap.min.js`, `ScrollTrigger.min.js`: `dist/` of npm `gsap@3.15.0`, unchanged
  (GSAP standard no-charge license, https://gsap.com/standard-license).

To upgrade: put the new files in a new versioned folder and change the paths in
`mainMap/templates/mainMap/landing.html` (import map) and `core/static/js/landing/main.js`.
