# Drought damage from groundwater abstraction: crops and nature

*Literature review, process chain, equations, Python options, and a complexity-vs-realism recommendation.*
*Prepared 12 Nov 2026.*

---

## 0. Short answer

No single Python package computes "drought damage from groundwater abstraction" from start to finish. The established method, used in the Netherlands and elsewhere, links four sub-models in a chain. Each link has a well-tested equation and a Python package:

| Link | What it computes | Core equation | Python |
|---|---|---|---|
| 1. Abstraction → drawdown | Head decline in the aquifer and in the phreatic water table | Theis / Hantush–Jacob / De Glee | `timflow` (TimML+TTim), `ttim`, `flopy` (MODFLOW), `pastas` (from observed heads) |
| 2. Water table → root-zone water supply | Less capillary rise from a deeper water table | Gardner (1958) steady capillary flux, or Richards' equation | `pyswap` (wraps SWAP), your own 1-D bucket |
| 3. Root-zone water → transpiration deficit | Reduced root water uptake | Feddes et al. (1978) α(h); FAO-56 Ks | inside SWAP / AquaCrop / PCSE, or your own code |
| 4a. Transpiration deficit → crop yield loss | % yield loss (drought, also oxygen and salt stress) | Doorenbos & Kassam Ky; WOFOST | `pcse` (WOFOST), `aquacrop` (AquaCrop-OSPy), `pyswap` (SWAP-WOFOST) |
| 4b. Stress → nature damage | Loss of target vegetation / goal realisation | Waternood trapezoid on GVG/GLG; PROBE (stress → indicator values → probability of vegetation type) | No pip package; Waterwijzer Natuur is a KWR desktop tool. Implement the equations yourself |

**Damage from abstraction is always a difference between two runs:** with abstraction minus without abstraction, run over a long series of real weather (≥30 years), then summarised as a mean and as dry-year percentiles. Never run a model only for the "drawdown".

---

## 1. Academic and technical sources

### 1.1 Crop drought damage (agriculture)
1. **Hack-ten Broeke, M.J.D., Kroes, J.G., Bartholomeus, R.P., van Dam, J.C., de Wit, A.J.W., Supit, I., Walvoort, D.J.J., van Bakel, P.J.T., Ruijtenberg, R. (2016).** Quantification of the impact of hydrology on agricultural production as a result of too dry, too wet or too saline conditions. *SOIL* 2, 391–402. doi:10.5194/soil-2-391-2016. Methodological basis of **Waterwijzer Landbouw (WWL)**: coupled SWAP-WOFOST runs, then a statistical meta-model that gives yield loss as a function of soil type and groundwater regime.
2. **Hack-ten Broeke, M.J.D., Mulder, H.M., Bartholomeus, R.P., et al. (2019).** Quantitative land evaluation implemented in Dutch water management. *Geoderma* 338, 536–545. doi:10.1016/j.geoderma.2018.11.002. Operational WWL. The meta-model is fitted to runs for ≥72 soil units and the full range of Dutch groundwater regimes, and is applied through the "WWL-tabel". Funders include the Advisory Commission for Groundwater Damage (ACSG) and the drinking-water companies, which shows the abstraction-damage use case.
3. **Kroes, J.G., van Dam, J.C., Bartholomeus, R.P., et al. (2017).** SWAP version 4: Theory description and user manual. Wageningen Environmental Research Report 2780. Current release: SWAP 4.3.0 (2026), LGPL. The reference for every process equation below (Richards' equation, root uptake, oxygen stress, WOFOST coupling).
4. **Feddes, R.A., Kowalik, P.J., Zaradny, H. (1978).** *Simulation of field water use and crop yield.* Pudoc, Wageningen. Origin of the α(h) root-water-uptake reduction function.
5. **Doorenbos, J., Kassam, A.H. (1979).** *Yield response to water.* FAO Irrigation & Drainage Paper 33. Origin of the Ky relationship. Updated in **Steduto et al. (2012), FAO I&D Paper 66** (AquaCrop).
6. **Werkgroep HELP-tabel (1987)**, Mededelingen Landinrichtingsdienst 176, and **Bouwmans (1990)**, TCGB-tabel. These are the legacy Dutch damage tables. They are useful for history and validation, but they are long-term averages based on outdated climate data and farming practice. WWL replaces them.
7. **Massop, H.Th.L., Kroes, J.G., Vroon, H.R.J., Mulder, H.M. (2014).** Pilot SWAP berekening droogteschade: vergelijking met de TCGB-tabel voor de waterwinning Vierlingsbeek. Alterra. A direct case study of a drinking-water abstraction, comparing a process model with a table. The process model gave lower abstraction damage than the table.
8. **WWL documentation:** *Toelichting Waterwijzer Landbouw 3.0.0* and *WWL-tabel* manual (waterwijzerlandbouw.wur.nl). Inputs are land use, BOFEK2020 soil unit, irrigation, weather station, and **GHG/GLG** (mean highest and lowest groundwater level). Outputs are yield loss split into drought, oxygen and salt stress, and direct versus indirect effects.

### 1.2 Nature / vegetation drought damage
9. **Witte, J.P.M., Bartholomeus, R.P., van Bodegom, P.M., et al. (2015).** A probabilistic eco-hydrological model to predict the effects of climate change on natural vegetation at a regional scale. *Landscape Ecology* 30(5), 835–854. This is **PROBE**: habitat factors (moisture/stress, nutrients, acidity) → plant-trait indicator values → occurrence probability of vegetation types.
10. **Bartholomeus, R.P., Witte, J.P.M., van Bodegom, P.M., van Dam, J.C., Aerts, R. (2008).** Critical soil conditions for oxygen stress to plant roots: substituting the Feddes-function by a process-based model. *J. Hydrology* 360, 147–165. doi:10.1016/j.jhydrol.2008.07.029. Relevant because abstraction also *reduces* wet/oxygen stress, so the net effect on nature needs both stresses.
11. **Bartholomeus, R.P., et al. (2012).** Process-based proxy of oxygen stress surpasses indirect ones in predicting vegetation characteristics. *Ecohydrology* 5(6), 746–758. Shows that process-based stress proxies generalise better under climate change than GVG/sum-exceedance proxies.
12. **Bartholomeus, R.P. (2013).** *Ecohydrological Stress – Groundwater To Stress Transfer (GTST)*, KWR 2013.088. Transfer functions from groundwater levels to drought stress and oxygen stress per soil and climate. This is an emulator, close to what you would build yourself.
13. **Witte, J.P.M., et al. (2018); Nijp, J., Bartholomeus, R.P., et al. (2022, STOWA 2022-08).** **Waterwijzer Natuur (WWN)** v1–3. Combines PROBE (prediction) with Waternood (testing via goal realisation).
14. **Eamus, D., Zolfaghar, S., Villalobos-Vega, R., Cleverly, J., Huete, A. (2015).** Groundwater-dependent ecosystems: recent insights from satellite and field-based studies. *HESS* 19, 4229–4256. International review. Includes a depth-to-groundwater threshold beyond which ecosystem structure and function change.
15. **Kath, J., Reardon-Smith, K., Le Brocque, A.F., et al. (2014).** Groundwater decline and tree change in floodplain landscapes: identifying non-linear threshold responses in canopy condition. *Global Ecology and Conservation* 2, 148–160. Empirical threshold approach for tree canopy dieback. Useful outside the Netherlands, where no process chain is available.

### 1.3 Groundwater drawdown
16. **Theis (1935); Hantush & Jacob (1955); De Glee (1930/1951)**: classical well-hydraulics solutions (any groundwater textbook, e.g. Kruseman & de Ridder, *Analysis and Evaluation of Pumping Test Data*).
17. **Bakker, M. (2013).** Semi-analytic modeling of transient multi-layer flow with TTim. *Hydrogeology Journal* 21, 935–943. TTim, now merged with TimML into **`timflow`** (2026).
18. **Collenteur, R.A., Bakker, M., Caljé, R., Klop, S.A., Schaars, F. (2019).** Pastas: open source software for the analysis of groundwater time series. *Groundwater*. doi:10.1111/gwat.12925.
19. **Brakenhoff, D.A., Vonk, M.A., Collenteur, R.A., Van Baar, M., Bakker, M. (2022).** Application of time series analysis to estimate drawdown from multiple well fields. *Front. Earth Sci.* 10:907609. Uses the Hantush response function in Pastas to separate abstraction effects from weather effects in observed heads.

### 1.4 Capillary rise
20. **Gardner, W.R. (1958).** Some steady-state solutions of the unsaturated moisture flow equation with application to evaporation from a water table. *Soil Science* 85, 228–232.

---

## 2. The process: how abstraction causes drought damage

```
Pumping Q ──► head decline in pumped aquifer s_a(r,t)
                │  (filtered by aquitard resistance c and surface-water drainage w)
                ▼
          phreatic water-table decline s_p(r,t)  ──► GHG/GLG shift deeper
                │
                ▼
   distance water table → root zone ↑  ⇒  capillary rise q_cap ↓ (exponentially)
                │
                ▼
   root-zone depletion ↑ in dry spells  ⇒  soil suction h ↓ (more negative)
                │
                ▼
   root water uptake reduced: T_a = α(h)·T_p  ⇒  transpiration deficit
                │
       ┌────────┴──────────┐
       ▼                   ▼
 CROPS: yield loss     NATURE: drought stress ↑, oxygen stress ↓
 1-Ya/Yx = Ky(1-Ta/Tp) ⇒ moisture indicator shifts drier
 (or WOFOST dynamics)  ⇒ wet, groundwater-dependent vegetation types lose
                         probability / goal realisation
```

Key physical insights that drive results:

* **Damage is concentrated where the water table is shallow enough to feed the root zone.** Capillary rise falls exponentially with distance. Where the water table is already deep (e.g. > ~2–3 m in coarse sand), extra drawdown causes little *additional* drought damage. Where it is ~0.8–2 m, a few decimetres can matter a lot. The relationship is strongly **non-linear and has a threshold** (see the demo in §5).
* **Drawdown in the pumped aquifer is not drawdown at the root zone.** In layered systems the phreatic drawdown is damped by the aquitard resistance *c* and buffered by ditches and streams (drainage resistance *w*). This filter is often the largest single uncertainty.
* **Damage is year-dependent.** Most damage occurs in dry years (in the Netherlands, e.g. 1976, 2018). Long-term averages hide this, which is why the HELP tables were replaced.
* **There are two-sided effects.** Lowering a high water table *reduces* wet damage (oxygen stress) for crops. It can *increase* or *decrease* the suitability of a site for a given nature target. Report drought damage, wet damage and the net effect separately.

---

## 3. The mathematics

### 3.1 Drawdown in the aquifer

**Confined, transient (Theis 1935)**

$$ s(r,t)=\frac{Q}{4\pi T}\,W(u),\qquad u=\frac{r^2 S}{4Tt},\qquad W(u)=E_1(u)=\int_u^\infty \frac{e^{-x}}{x}\,dx $$

**Leaky aquifer, steady (De Glee)**: the usual choice for Dutch layered aquifers:

$$ s(r)=\frac{Q}{2\pi T}\,K_0\!\left(\frac{r}{\lambda}\right),\qquad \lambda=\sqrt{T\,c} $$

**Leaky, transient (Hantush–Jacob 1955):** $s=\frac{Q}{4\pi T}W(u,r/\lambda)$, with the Hantush well function.

Symbols: Q pumping rate [m³/d], T transmissivity [m²/d], S storativity [–], c vertical resistance of the aquitard [d], λ leakage factor [m], K₀ the modified Bessel function.

### 3.2 From aquifer drawdown to phreatic drawdown

Steady-state approximation for a phreatic top system with drainage resistance *w* [d] above an aquitard with resistance *c* [d], with horizontal flow in the top layer neglected (resistances in series):

$$ s_p \approx s_a\,\frac{w}{w+c} $$

High *c* (thick clay or peat) or low *w* (dense ditch network) means little phreatic drawdown. On sandy soils without ditches, *w* is large and s_p ≈ s_a. Use a multi-layer model (`timflow`/`ttim`/MODFLOW) when this approximation is too crude.

### 3.3 Capillary rise from the water table (Gardner 1958)

Use the exponential conductivity function $K(\psi)=K_s e^{-\alpha\psi}$ (ψ = suction, positive [m]) and Darcy's law for upward flux q, with z measured upward from the water table:

$$ q = K(\psi)\left(\frac{d\psi}{dz}-1\right) \;\Rightarrow\; z=\int_0^{\psi}\frac{K}{q+K}\,d\psi=\frac{1}{\alpha}\ln\frac{q+K_s}{q+K_s e^{-\alpha\psi}} $$

Solve for the flux reaching the bottom of the root zone at height z, where suction is ψ:

$$ q=K_s\,\frac{e^{-\alpha z}-e^{-\alpha\psi}}{1-e^{-\alpha z}},\qquad q_{\max}=\lim_{\psi\to\infty}q=\frac{K_s}{e^{\alpha z}-1} $$

Here z = groundwater depth − root-zone depth. **This expression is where groundwater abstraction enters the soil water balance.** A drawdown Δz multiplies q_max by roughly $e^{-\alpha\Delta z}$. Typical values: α ≈ 1–2 m⁻¹ for loam/clay (high capillary rise over long distances) and α ≈ 4–8 m⁻¹ for coarse sand (capillary rise collapses within decimetres).

### 3.4 Root-zone water balance and transpiration reduction

Daily bucket for the root zone (depletion D_r [mm], total available water TAW):

$$ D_{r,i}=D_{r,i-1}-P_i-I_i-q_{cap,i}+ET_{a,i}+DP_i $$

**Feddes et al. (1978)** reduction as a function of pressure head h (h₁ > h₂ > h₃ > h₄, all ≤ 0):

$$ \alpha(h)=\begin{cases}0 & h>h_1 \ \text{(anaerobic)}\\ \dfrac{h_1-h}{h_1-h_2} & h_2<h\le h_1\\ 1 & h_3\le h\le h_2\\ \dfrac{h-h_4}{h_3-h_4} & h_4\le h<h_3\\ 0 & h<h_4 \ \text{(wilting)}\end{cases} \qquad T_a=\int_{root} \alpha(h)\,S_{max}(z)\,dz $$

h₃ depends on atmospheric demand T_p (it is wetter at high T_p). The wet branch (h₁, h₂) is the oxygen-stress part. Bartholomeus et al. (2008) show that this branch starts too late and propose a process-based replacement.

**Bucket equivalent (FAO-56):** $K_s = \frac{TAW-D_r}{(1-p)\,TAW}$ for $D_r>p\,TAW$, otherwise 1, and $ET_a=K_s\,K_c\,ET_0$.

### 3.5 From transpiration deficit to yield loss

**Doorenbos & Kassam (1979):**

$$ 1-\frac{Y_a}{Y_x}=K_y\left(1-\frac{ET_a}{ET_x}\right) $$

Ky ≈ 1.0–1.25 for most arable crops and grass, and is stage-dependent. A dynamic alternative is WOFOST (PCSE, or inside SWAP), which reduces daily CO₂ assimilation by T_a/T_p and integrates over the growing season.

**Abstraction damage per year *j* and summary:**

$$ \Delta L_j = L_j^{\,\text{with}} - L_j^{\,\text{without}},\qquad \overline{\Delta L}=\frac1N\sum_j \Delta L_j,\quad \Delta L_{90}=\text{90th percentile} $$

Optionally convert to money: € = ΔL × potential yield × price. WWL also reports indirect effects, such as delayed workability and harvest losses, on top of the direct transpiration-based loss.

### 3.6 Nature damage

**(a) Waternood goal realisation (testing; simple).** For each target vegetation type, goal realisation is a trapezoid function of a groundwater characteristic x (GVG, the mean spring level, or GLG), with break-points A1 < A2 ≤ B2 < B1 (cm below surface):

$$ GR(x)=\begin{cases}0 & x\le A_1 \text{ or } x\ge B_1\\ \dfrac{x-A_1}{A_2-A_1} & A_1<x<A_2\\ 1 & A_2\le x\le B_2\\ \dfrac{B_1-x}{B_1-B_2} & B_2<x<B_1\end{cases},\qquad \Delta GR = GR(x+s_p)-GR(x) $$

Break-points per vegetation type come from Waternood / Runhaar et al. (published in STOWA reports).

**(b) PROBE / Waterwijzer Natuur (prediction; process-based).**
1. From a SWAP-type simulation, compute **drought stress** (transpiration deficit of a reference vegetation; WWN uses the maximum deficit over a contiguous ~10-day period) and **oxygen stress** (root respiration stress) for each year.
2. Translate the stresses, together with nutrient availability and acidity, into **indicator values** (e.g. Ellenberg/Runhaar moisture indication) with empirical regressions.
3. Compute the **occurrence probability** of each vegetation type (Witte et al. 2015; multinomial/logistic regression on the indicator values) and weight it by its conservation value.

Damage = Δ probability × conservation value, summed over the area.

**(c) Data-driven thresholds (outside the Netherlands).** Fit canopy condition (NDVI/field scores) against depth to groundwater and detect thresholds (Kath et al. 2014: boosted regression trees, quantile regression, TITAN). Damage = probability of crossing the threshold under the drawdown.

---

## 4. Python packages: what each does and how it fits

| Package | Role in the chain | Notes |
|---|---|---|
| **`timflow`** (`pip install timflow`) | Drawdown, steady and transient, multi-layer, analytic elements | 2026 merger of TimML and TTim (M. Bakker, TU Delft). No grid needed. Ideal for wells in Dutch layered aquifers. `ttim` (0.8) still works as a standalone package. |
| **`pastas`** | Drawdown *from data*: fits head = recharge response + well response (Hantush impulse response) | Best when observation wells exist. Gives an empirical s_p directly, including uncertainty. |
| **`flopy`** | MODFLOW 6 builder | Use it for complex geology or many wells, or for coupling with an unsaturated-zone model. |
| **`pyswap`** (wrapper, not a reimplementation) | Runs SWAP 4 (Richards' equation + Feddes/oxygen stress + WOFOST) per soil column, with groundwater depth as a bottom boundary | The same engine as Waterwijzer Landbouw. Heavy but closest to "Dutch standard practice". Needs the SWAP executable. |
| **`pcse`** (v6) | WOFOST 7.x/8.x crop growth in pure Python | Has its own simple water balance (no groundwater-table capillary rise by default). Combine it with your own §3.3 flux, or use SWAP. |
| **`aquacrop`** (AquaCrop-OSPy) | Water-driven crop model with an optional groundwater table | Good internationally and easy to use. Salinity stress is not yet implemented. |
| your own module | §3.2–3.5 as a daily bucket | Fast enough for millions of cells × 30 years. Calibrate it against SWAP (see §6). |

There is **no Python package for Waterwijzer Natuur, PROBE or the WWL-tabel**. WWL-tabel is a web tool/API from WUR, and WWN is a KWR tool. For a scientific tool, either (i) call the WWL web tool or API for the Dutch crop case, or (ii) implement §3.6 yourself and use WWN/WWL outputs for validation. Two R packages (`helptabel`/`hlptabel`, C.H. van Immerzeel) reproduce the legacy HELP-1987 table and can serve as a benchmark.

---

## 5. Reference implementation (minimal, tested)

```python
import numpy as np
from scipy.special import exp1, k0

# --- 1. Drawdown -------------------------------------------------------
def theis(Q, T, S, r, t):                       # m3/d, m2/d, -, m, d
    return Q / (4*np.pi*T) * exp1(r**2 * S / (4*T*t))

def de_glee(Q, T, c, r):                         # steady leaky aquifer
    return Q / (2*np.pi*T) * k0(r / np.sqrt(T*c))

def phreatic_fraction(c, w):                     # aquitard c, drainage w [d]
    return w / (w + c)

# --- 2. Capillary rise (Gardner 1958) ---------------------------------
def gardner_qmax(Ks, alpha, z):                  # m/d, 1/m, m above water table
    return Ks / np.expm1(alpha * z)

# --- 3. Root-zone stress (FAO-56 form of Feddes dry branch) ------------
def stress_coeff(Dr, TAW, p):
    return np.clip((TAW - Dr) / ((1 - p) * TAW), 0, 1)

def simulate(P, ETp, gw_depth, root_depth=0.3, TAW=60., p=0.5, Ks=0.2, alpha=4.0):
    """Daily bucket. P, ETp [mm/d]; gw_depth [m below surface] per day."""
    Dr, ETa = 0.0, np.zeros_like(P)
    for i in range(len(P)):
        z = max(gw_depth[i] - root_depth, 0.05)
        cap = min(gardner_qmax(Ks, alpha, z) * 1000, Dr)   # supply limited by deficit
        ETa[i] = stress_coeff(Dr, TAW, p) * ETp[i]
        Dr = np.clip(Dr - P[i] - cap + ETa[i], 0, TAW)
    return ETa

# --- 4. Yield loss -----------------------------------------------------
def yield_loss(ETa, ETp, Ky=1.0):
    return Ky * (1 - ETa.sum() / ETp.sum())

# --- Abstraction damage = with - without -------------------------------
def abstraction_damage(P, ETp, gw_base, s_phreatic, **kw):
    l0 = yield_loss(simulate(P, ETp, gw_base, **kw), ETp)
    l1 = yield_loss(simulate(P, ETp, gw_base + s_phreatic, **kw), ETp)
    return l1 - l0
```

Demo: Q = 2000 m³/d, T = 500 m²/d, c = 500 d, w = 100 d, r = 300 m. The aquifer drawdown is 0.49 m and the phreatic drawdown 0.08 m. Synthetic dry summer (180 d, ET_p = 3 mm/d), sandy soil (α = 4 m⁻¹):

| Baseline water table | q_max at root zone | Loss without | Loss with | **Abstraction damage** |
|---|---|---|---|---|
| 1.0 m | 13 mm/d | 0 % | 0 % | 0 |
| 1.3 m | 3.7 mm/d | 0 % | 0 % | 0 |
| 1.6 m | 1.1 mm/d | 0 % | 0.1 % | 0.1 %-pt |
| 2.0 m | 0.2 mm/d | 11.5 % | 13.4 % | **1.9 %-pt** |

The same 8 cm drawdown does nothing where capillary rise exceeds demand and costs about 2 %-points where the system is near its threshold. This non-linearity is why the static depth-to-damage tables were inadequate. (These are illustrative numbers, not calibrated values.)

For production use: replace the bucket with the van Genuchten–Mualem parameters of the actual soil (Staring series / BOFEK2020 in the Netherlands), let q_cap depend on the actual root-zone suction (full Gardner expression in §3.3), add the wet branch for oxygen stress, and run over ≥30 years of KNMI (or local) daily weather.

---

## 6. Complexity vs realism: where the balance lies

### 6.1 Ladder of options

| Tier | Method | Realism | Cost / data | Main failure mode |
|---|---|---|---|---|
| **0** | Lookup tables (HELP 1987, TCGB) | Low | Trivial | Outdated climate and farming practice; long-term averages only; no dry-year signal. Replaced in Dutch practice. |
| **1** | Drawdown (analytical) → GHG/GLG shift → **WWL-tabel** (crops) / **Waternood trapezoid** (nature) | Medium (NL) | Low | Static GHG/GLG description of the regime; WWL-tabel overestimates wet damage at very shallow GHG (< ~20 cm). Netherlands only. |
| **2** | Drawdown (`timflow`/`pastas`) → **daily 1-D bucket with Gardner capillary rise + Feddes/FAO-56 + Ky** over 30 years; nature via stress → indicator → probability | Medium–high | Moderate; fast for whole regions | Bucket misses vertical moisture profiles and layered soils. Needs calibration of α, TAW and root depth. |
| **3** | Drawdown (MODFLOW/`timflow`) → **SWAP-WOFOST per soil unit (`pyswap`)** with a dynamic groundwater bottom boundary; WWN/PROBE for nature | High | High: soil hydraulic data, executable, CPU | Parameter uncertainty (soil physics, roots) often exceeds the structural gain. Hard to run per pixel. |
| **4** | Fully coupled groundwater–unsaturated zone (MODFLOW + MetaSWAP, as in the Dutch NHI/LHM) | Highest | Very high | Overkill for a tool. Calibration burden. |

### 6.2 What actually controls realism (prioritise these)
1. **Phreatic drawdown, not aquifer drawdown.** Getting *c* and *w* right (§3.2), or measuring s_p with Pastas, matters more than any crop-model detail.
2. **Capillary rise physics (soil type and α).** This is the most sensitive link. A sand-versus-loam error changes damage by a factor >5. Use measured or mapped soil hydraulic functions.
3. **Interannual weather.** Run a ≥30-year daily series and report dry-year percentiles. A single "average year" underestimates damage.
4. **Root-zone depth.** It sets the distance z. WWL 3.0 revised its root-development assumptions specifically because this mattered.
5. **Two-sided stress.** Include oxygen stress so the net effect is correct where water tables are shallow.

Things that add complexity with small returns for *drought damage due to abstraction*: full Richards' equation where the water table is deep (capillary contribution is ~0 either way), nitrogen-limited crop growth, and sub-daily time steps.

### 6.3 Recommendation

**Build the tool on Tier 2 and calibrate it with Tier 3. This is the meta-model approach that Waterwijzer Landbouw itself uses.**

1. **Drawdown:** `timflow` for scenario wells (or `pastas` where head series exist). Convert to phreatic drawdown with explicit c and w.
2. **Emulator:** for each soil class, run SWAP-WOFOST via `pyswap` over a grid of baseline depths × drawdowns × 30 weather years. Fit the bucket parameters (TAW, α, root depth) or a direct meta-relation $\Delta L = f(\text{soil}, GHG, GLG, s_p, \text{year type})$ (gradient boosting or monotone splines).
3. **Runtime:** the tool evaluates the emulator per cell. This takes milliseconds, so uncertainty analysis (Monte Carlo on c, w, α) is feasible. That is more valuable than the extra realism of running SWAP live.
4. **Validation:** compare with WWL-tabel results for Dutch cases (and with WWN for nature), and with the literature case of Vierlingsbeek (Massop et al. 2014).
5. **Nature module:** start with the Waternood trapezoid (transparent, quick). Add a stress-based PROBE-type step when you need climate-robust predictions. Use empirical depth thresholds (Kath, Eamus) for non-Dutch GDEs.

This gives about 80–90 % of the realism of the full process chain at a small fraction of the cost. The remaining gap is dominated by input uncertainty (soil physics, phreatic coupling), which no model tier removes.

---

## 7. Links
- Waterwijzer Landbouw: https://waterwijzerlandbouw.wur.nl/ (WWL-tabel manual: https://www.waterwijzerlandbouw.wur.nl/downloads/3.0/WWL_tabel.pdf)
- Hack-ten Broeke et al. 2016: https://soil.copernicus.org/articles/2/391/2016
- Hack-ten Broeke et al. 2019: https://doi.org/10.1016/j.geoderma.2018.11.002
- SWAP 4 manual: https://swap.wur.nl/Documents/Kroes_etal_2017_SWAP_version_4_ESG_Report_2780.pdf
- pySWAP: https://pypi.org/project/pyswap/ · https://github.com/zawadzkim/pyswap
- timflow: https://pypi.org/project/timflow/ · TTim: https://github.com/mbakker7/ttim
- Pastas: https://pastas.readthedocs.io/ · Brakenhoff et al. 2022: https://doi.org/10.3389/feart.2022.907609
- PCSE/WOFOST: https://pcse.readthedocs.io/
- AquaCrop-OSPy: https://github.com/aquacropos/aquacrop
- Bartholomeus et al. 2008: https://doi.org/10.1016/j.jhydrol.2008.07.029
- Witte et al. 2015 (PROBE): Landscape Ecology 30(5):835–854
- GTST manual: https://api.kwrwater.nl/uploads/2022/09/KWR-2013.088-Ecohydrological-Stress-Groundwater-To-Stress-Transfer-(OPENBAAR).pdf
- Waterwijzer Natuur: https://www.kwrwater.nl/tools-producten/waterwijzer-natuur/ · STOWA 2022-08
- Eamus et al. 2015: https://doi.org/10.5194/hess-19-4229-2015
- Kath et al. 2014: https://doi.org/10.1016/j.gecco.2014.09.002
- FAO 33 / FAO 66: https://www.fao.org/4/i2800e/i2800e.pdf
