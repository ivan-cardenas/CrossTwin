"""Check the architecture diagram palette (tools/arch_diagrams.py PALETTE) for legibility
and colour-blind separation. Exits 1 if a rule fails, so it can run before regenerating.

    python tools/palette_check.py

Rules:
  * white text on each stroke colour (tags, box headers) >= MIN_WHITE_CONTRAST (WCAG ratio)
  * each kind's text colour on its own fill >= MIN_TEXT_CONTRAST
  * every pair of stroke colours >= MIN_DELTA_E apart (CIE76 on CIELAB) under normal vision
    and simulated deuteranopia, protanopia and tritanopia (Machado et al. 2009, severity 1.0)
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arch_diagrams import PALETTE  # noqa: E402

MIN_WHITE_CONTRAST = 4.0
MIN_TEXT_CONTRAST = 7.0
MIN_DELTA_E = 9.0

# Linear-RGB simulation matrices (Machado, Oliveira & Fernandes 2009)
CVD = {
    "normal": None,
    "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}


def linear_rgb(hex_colour):
    h = hex_colour.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]


def luminance(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted([luminance(linear_rgb(a)), luminance(linear_rgb(b))], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def simulate(rgb, matrix):
    if matrix is None:
        return rgb
    return [min(1.0, max(0.0, sum(matrix[i][j] * rgb[j] for j in range(3)))) for i in range(3)]


def lab(rgb):
    r, g, b = rgb
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = luminance(rgb)
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(a, b):
    return sum((p - q) ** 2 for p, q in zip(lab(a), lab(b))) ** 0.5


def main():
    failures = []
    print(f"{'kind':10}{'stroke':10}{'white':>7}{'text':>7}")
    for kind, (stroke, fill, text) in PALETTE.items():
        white, own = contrast("#ffffff", stroke), contrast(text, fill)
        print(f"{kind:10}{stroke:10}{white:7.2f}{own:7.2f}")
        if white < MIN_WHITE_CONTRAST:
            failures.append(f"{kind}: white on {stroke} is {white:.2f}:1 (< {MIN_WHITE_CONTRAST})")
        if own < MIN_TEXT_CONTRAST:
            failures.append(f"{kind}: {text} on {fill} is {own:.2f}:1 (< {MIN_TEXT_CONTRAST})")

    print("\nclosest pairs (dE):")
    for vision, matrix in CVD.items():
        sims = {k: simulate(linear_rgb(v[0]), matrix) for k, v in PALETTE.items()}
        pairs = sorted((delta_e(sims[a], sims[b]), a, b) for a, b in itertools.combinations(sims, 2))
        print(f"  {vision:7}" + ", ".join(f"{a}/{b} {d:.0f}" for d, a, b in pairs[:3]))
        failures += [f"{vision}: {a}/{b} only dE {d:.1f} apart (< {MIN_DELTA_E})"
                     for d, a, b in pairs if d < MIN_DELTA_E]

    if failures:
        print("\nFAIL\n  " + "\n  ".join(failures))
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
