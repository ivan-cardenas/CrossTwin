"""
Hedonic price model (Phase 4 of docs/ACCESSIBILITY_PLAN.md): how much of the WOZ value per m2 of an area
goes with how reachable each kind of amenity is.

    ln(WOZ per m2)_a = a + SUM_t b_t T(A_t,a) + controls_a + municipality_c(a) + e_a

weighted by the area's dwellings, errors clustered by municipality (by neighborhood with one municipality).
The unit `a` is a PC6 postcode area (housing.PostcodePrice: a street section, so a municipality has hundreds
of them). A term `t` is one amenity category on one mode ("walk:supermarket", "bike:train_station", ...);
A_t,a is the area's frozen baseline of that term, 0-100 (builtup chain.category_value x 100), T the identity or
ln(1 + A). The result is an association across areas, an upper bound, not a causal effect or a forecast: it
credits accessibility with everything that goes with it (prestige, jobs, older housing).

Steps of fit_hedonic() (pure: rows in, a dict of PriceModel fields out):
1. Controls: kept when at least MIN_CONTROL_COVERAGE of the areas have them; rows missing a kept control are dropped.
2. Screening of the candidate terms (screen_terms), each drop recorded with its reason in `screening`:
   a. too little variation: a term that is (almost) constant across the areas cannot be estimated;
   b. redundant: two terms with |r| >= REDUNDANT_CORR measure the same thing, the one that tracks the price less
      is dropped;
   c. collinear: terms are dropped one at a time, highest variance inflation factor first, until every VIF is
      at most VIF_MAX (Kutner et al. 2005);
   d. too little influence: terms are dropped one at a time, weakest first, while one is not significant
      (p > INFLUENCE_P) or moves the price by less than MIN_EFFECT_PER_SD per standard deviation of the term.
3. Functional form: linear against ln(1 + A), compared by AIC and by spatially blocked cross-validated R2 (the
   comparison drops the municipality effects, because a held-out municipality has none). A natural cubic spline
   is fitted as a diagnostic only: the equation needs one beta per term, so the stored form is one of the two.
4. Spatial autocorrelation: Moran's I of the residuals (queen contiguity of the area polygons,
   permutation p-value, fixed seed). When it is significant a spatial error model is fitted (lambda by ML,
   spreg.ML_Error; coefficients by weighted least squares on the spatially filtered data) and the betas of the
   model whose residuals pass the diagnostic are stored.
5. The same terms without the controls are stored beside it: how much the controls move the betas.

Heavy libraries are imported inside the functions. Decision rules and constants below are design choices,
not estimates: they are named so a different choice is a new, visible method.

References: Rosen (1974) J. Political Economy 82 (hedonic prices); Anselin (1988) Spatial Econometrics
(spatial error model); Moran (1950) Biometrika 37; Roberts et al. (2017) Ecography 40 (blocked cross-validation);
Kutner, Nachtsheim, Neter & Li (2005) Applied Linear Statistical Models, 5th ed. (variance inflation factor).

6. The prediction (`PriceModel.prediction`): the one equation of the whole city (intercept, term betas, control
   coefficients, municipality effects, smearing factor). A dwelling's price is that equation applied to its own
   variables; the WOZ value of its area is only what the model was calibrated on.

DAG edges: Accessibility -> Property (the fitted betas)
"""
import logging
import math
from collections import Counter

from . import chain

logger = logging.getLogger(__name__)

MIN_AREAS = 30                       # fewer areas than this are not fitted at all
EXPLORATORY_MIN_AREAS = 8            # the exploratory fit (no controls) checks the pipeline on a small area; its betas are not interpretable
MIN_OBS_PER_PARAMETER = 5            # a fit needs this many areas per estimated parameter (terms, controls, intercept, municipality effects) after the screening; the usual floor of 5-10 per predictor in OLS
MIN_CONTROL_COVERAGE = 0.8           # a control present in less of the areas is dropped, not imputed
MIN_TERM_SD = 1.0                    # a term whose dwelling-weighted standard deviation is under this many score points (0-100) is too constant to estimate
MIN_TERM_PRESENCE = 0.02             # ... or that is above zero in under this share of the areas (the amenity is out of reach nearly everywhere)
REDUNDANT_CORR = 0.90                # two terms correlated at least this much (|r|, dwelling-weighted) are one measurement: the weaker one is dropped
VIF_MAX = 10.0                       # variance inflation factor above which a term is dropped (rule of thumb, Kutner et al. 2005)
INFLUENCE_P = 0.10                   # a term that is not significant at this level (clustered errors) has no detectable influence
MIN_EFFECT_PER_SD = 0.005            # a term that moves the price by less than this (log points, about 0.5 %) per standard deviation of the term is negligible even if significant
MIN_AREA_COVERAGE = 0.8              # an area is fitted only when the dwellings its mean area is taken over are at least this share of the CBS dwelling stock
CONSTRUCTION_YEAR_RANGE = (1600, 2100)   # BAG holds placeholders (e.g. 1005): outside this range the year is ignored
# Energy label as an ordinal, G = 1 ... A+++ = 10 (the label choices of Energy.EnergyEfficiencyLabels, A++++ added by RVO)
ENERGY_ORDINAL = {"G": 1, "F": 2, "E": 3, "D": 4, "C": 5, "B": 6, "A": 7, "A+": 8, "A++": 9, "A+++": 10, "A++++": 11}
CONTROLS = ("constructionYear", "apartmentShare", "rentalShare", "energyLabel", "ses", "distCentre_km")

MORAN_PERMUTATIONS = 999
MORAN_SEED = 20261126                # stored with every fit
MORAN_ALPHA = 0.05
CV_FOLDS = 5
CV_MIN_MUNICIPALITIES = 5            # blocks = municipalities from this many, else a grid of the neighborhood centroids
CV_GRID = 3
SPLINE_DF = 4
SPLINE_FLAG_GAIN = 0.02              # the spline is flagged when its cross-validated R2 beats the stored form by this much
MIN_CLUSTERS = 2                     # municipalities needed for municipality effects; clusters (municipalities, else PC4 areas) needed for clustered errors
FEW_CLUSTERS = 10                    # below this the clustered errors are flagged as unreliable
SEM_FULL_MAX_N = 500                 # spreg.ML_Error uses the dense log-determinant up to this many neighborhoods, the sparse LU beyond


class PriceModelError(Exception):
    """The fit cannot be made (too few neighborhoods, no variation); the message is shown to the staff user."""


# ── spatial helpers ────────────────────────────────────────────────

def queen_neighbors(polygons):
    """{i: [j, ...]} of the polygons that share at least a point with polygon i (queen contiguity)."""
    from shapely.strtree import STRtree

    tree = STRtree(polygons)
    neighbors = {i: [] for i in range(len(polygons))}
    for i, geom in enumerate(polygons):
        for j in tree.query(geom, predicate="intersects"):
            if int(j) != i:
                neighbors[i].append(int(j))
    return neighbors


def spatial_weights(polygons):
    """Row-standardised queen weights (libpysal.weights.W), ids 0..n-1 in the order of `polygons`."""
    import warnings

    from libpysal.weights import W

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # islands are expected at the edge of the imported area
        weights = W(queen_neighbors(polygons), ids=list(range(len(polygons))), silence_warnings=True)
        weights.transform = "r"
    return weights


def morans(residuals, weights, seed=MORAN_SEED, permutations=MORAN_PERMUTATIONS):
    """(Moran's I, pseudo p-value) of the residuals; two-sided permutation test with a fixed seed."""
    import numpy as np
    from esda.moran import Moran

    state = np.random.get_state()   # esda draws from the global generator: seed it, then put it back
    np.random.seed(seed)
    try:
        result = Moran(np.asarray(residuals, dtype=float), weights, permutations=permutations)
    finally:
        np.random.set_state(state)
    return float(result.I), float(result.p_sim)


# ── regression helpers ─────────────────────────────────────────────

def _col(term):
    """Column of a term in the fit frame: 'walk:supermarket' -> 'walk__supermarket' (a valid formula name)."""
    return term.replace(chain.TERM_SEP, "__")


def _xcol(term):
    """Column of the transformed term T(A) the regression uses."""
    return "x_" + _col(term)


def _term_of(name):
    """Term name of a regression coefficient name ('x_walk__supermarket' -> 'walk:supermarket'); None for others."""
    if not name.startswith("x_") or "__" not in name:
        return None
    mode, _, category = name[2:].partition("__")
    return chain.term_key(mode, category)


def _formula(form, controls, fixed_effects, terms, spline=False):
    cols = [_col(t) for t in terms]
    parts = [f"cr({c}, df={SPLINE_DF}, constraints='center')" for c in cols] if spline else [f"x_{c}" for c in cols]
    parts += list(controls)
    if fixed_effects:
        parts.append("C(city)")
    return "lnPrice ~ " + " + ".join(parts)


def _with_forms(frame, form, terms):
    import numpy as np

    frame = frame.copy()
    for term in terms:
        column = frame[_col(term)]
        frame[_xcol(term)] = np.log1p(column.clip(lower=0)) if form == "log1p" else column
    return frame


def _fit(formula, frame, clustered):
    import statsmodels.formula.api as smf

    model = smf.wls(formula, data=frame, weights=frame["weight"])
    if clustered:
        # t-distribution with G - 1 degrees of freedom: with a handful of clusters the normal one is too optimistic
        return model.fit(cov_type="cluster", cov_kwds={"groups": frame["cluster_code"].to_numpy()}, use_t=True)
    return model.fit(cov_type="HC1")


def _coefficients(res):
    """{name: {coef, se, p}} of a fit; a term's coefficient is stored under the term name ('walk:supermarket')."""
    return {_term_of(name) or name: {"coef": float(res.params[name]), "se": float(res.bse[name]), "p": float(res.pvalues[name])}
            for name in res.params.index}


def _folds(frame):
    """Fold number per row: municipalities as blocks from CV_MIN_MUNICIPALITIES of them, else a grid of centroids."""
    import numpy as np
    import pandas as pd

    if frame["city"].nunique() >= CV_MIN_MUNICIPALITIES:
        blocks = frame["city_code"].to_numpy()
    else:
        bx = pd.qcut(frame["x"].rank(method="first"), CV_GRID, labels=False).to_numpy()
        by = pd.qcut(frame["y"].rank(method="first"), CV_GRID, labels=False).to_numpy()
        blocks = bx * CV_GRID + by
    order = {block: i for i, block in enumerate(sorted(set(blocks.tolist())))}
    if len(order) < 2:
        return None
    return np.array([order[b] % CV_FOLDS for b in blocks.tolist()])


def _cv_r2(frame, form, controls, terms, folds, spline=False):
    """Weighted out-of-fold R2 of the model without municipality effects; None when it cannot be computed."""
    import numpy as np
    import statsmodels.formula.api as smf

    if folds is None or len(set(folds.tolist())) < 2:
        return None
    frame = _with_forms(frame, form, terms)
    formula = _formula(form, controls, False, terms, spline)
    predicted = np.full(len(frame), np.nan)
    try:
        for fold in sorted(set(folds.tolist())):
            train, test = frame[folds != fold], frame[folds == fold]
            if spline:   # a spline cannot be evaluated outside the range it was built on
                test = test.assign(**{_col(t): test[_col(t)].clip(train[_col(t)].min(), train[_col(t)].max()) for t in terms})
            res = smf.wls(formula, data=train, weights=train["weight"]).fit()
            predicted[(folds == fold)] = np.asarray(res.predict(test))
    except Exception:   # noqa: BLE001 - a singular fold or an out-of-range spline only drops the diagnostic
        logger.warning("Cross-validation of the %s form failed", "spline" if spline else form, exc_info=True)
        return None
    y, w = frame["lnPrice"].to_numpy(), frame["weight"].to_numpy()
    mean = np.average(y, weights=w)
    sst = float(np.sum(w * (y - mean) ** 2))
    return None if sst <= 0 else 1.0 - float(np.sum(w * (y - predicted) ** 2)) / sst


def _spatial_error(formula, frame, weights, clustered):
    """
    Spatial error model: lambda by ML (spreg.ML_Error on the unweighted data), then the coefficients by weighted
    least squares on the data filtered by (I - lambda W). Returns (result, coefficients, lambda, R2).
    """
    import numpy as np
    import patsy
    import statsmodels.api as sm
    from spreg import ML_Error

    y, x = patsy.dmatrices(formula, frame, return_type="dataframe")
    ml = ML_Error(y.to_numpy(), x.drop(columns="Intercept").to_numpy(), weights,
                  method="full" if len(frame) <= SEM_FULL_MAX_N else "LU")
    lam = float(np.ravel(ml.lam)[0])
    sparse = weights.sparse

    def filtered(values):
        values = np.asarray(values, dtype=float)
        return values - lam * (sparse @ values)

    y_f = filtered(y.to_numpy())[:, 0]
    x_f = filtered(x.to_numpy())
    model = sm.WLS(y_f, x_f, weights=frame["weight"].to_numpy())
    if clustered:
        res = model.fit(cov_type="cluster", cov_kwds={"groups": frame["cluster_code"].to_numpy()}, use_t=True)
    else:
        res = model.fit(cov_type="HC1")
    names = list(x.columns)
    coefs = {_term_of(name) or name: {"coef": float(res.params[i]), "se": float(res.bse[i]), "p": float(res.pvalues[i])}
             for i, name in enumerate(names)}
    # R2 of the mean structure on the original scale (weighted, centered): statsmodels' own R2 of the filtered fit
    # is uncentered, because the filtered intercept column is not exactly constant, and reads about 1
    weights_y = frame["weight"].to_numpy()
    observed = y.to_numpy()[:, 0]
    fitted = x.to_numpy() @ np.asarray(res.params)
    centre = np.average(observed, weights=weights_y)
    total = float(np.sum(weights_y * (observed - centre) ** 2))
    r2 = 1.0 - float(np.sum(weights_y * (observed - fitted) ** 2)) / total if total > 0 else None
    return res, coefs, lam, r2


# ── screening of the candidate terms ────────────────────────────────

def _num(value, digits=6):
    """A JSON-safe number: None for NaN and infinity (a JSON column cannot hold them)."""
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _weighted_sd(values, weights):
    import numpy as np

    mean = np.average(values, weights=weights)
    return float(np.sqrt(np.average((values - mean) ** 2, weights=weights)))


def _weighted_corr(frame, columns):
    """Dwelling-weighted correlation matrix of the columns (a constant column gets 0 against the others, 1 on its diagonal)."""
    import numpy as np

    data = frame[columns].to_numpy(dtype=float)
    weights = frame["weight"].to_numpy(dtype=float)
    centred = data - np.average(data, axis=0, weights=weights)
    cov = (centred * weights[:, None]).T @ centred / weights.sum()
    sd = np.sqrt(np.diag(cov))
    scale = np.outer(sd, sd)
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.where(scale > 0, cov / scale, 0.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def variance_inflation(frame, terms):
    """{term: VIF} of the terms among themselves (dwelling-weighted); inf when a term is a linear combination of the others."""
    import numpy as np

    if len(terms) < 2:
        return {t: 1.0 for t in terms}
    corr = _weighted_corr(frame, [_col(t) for t in terms])
    try:
        diag = np.diag(np.linalg.inv(corr))
    except np.linalg.LinAlgError:
        return {t: math.inf for t in terms}
    return {t: (float(v) if v > 0 and math.isfinite(v) else math.inf) for t, v in zip(terms, diag)}


def screen_terms(frame, candidates, controls, fixed_effects, clustered):
    """
    Choose the terms the price model keeps among `candidates` (the steps 2a-2d of the module docstring).
    Returns (kept terms, report): the report holds every candidate with its status ("kept" or "dropped"), the
    reason, its dwelling-weighted correlation with ln(price) and, for the kept ones, the final coefficient,
    standard error, p, effect per standard deviation and VIF. Deterministic: ties are broken by term name.
    """
    import numpy as np

    weights = frame["weight"].to_numpy(dtype=float)
    price = frame["lnPrice"].to_numpy(dtype=float)
    report = {}
    sd = {t: _weighted_sd(frame[_col(t)].to_numpy(dtype=float), weights) for t in candidates}
    with_price = {}
    for t in candidates:
        corr = _weighted_corr(frame.assign(_price=price), [_col(t), "_price"])[0, 1]
        with_price[t] = float(corr)
        report[t] = {"status": "kept", "reason": "", "sd": round(sd[t], 3), "corr_price": round(float(corr), 4)}

    def drop(term, reason):
        report[term].update(status="dropped", reason=reason)

    # a. too little variation
    alive = []
    for t in sorted(candidates):
        present = float((frame[_col(t)] > 0).mean())
        if sd[t] < MIN_TERM_SD:
            drop(t, f"too little variation (sd {sd[t]:.2f} < {MIN_TERM_SD:g} score points)")
        elif present < MIN_TERM_PRESENCE:
            drop(t, f"out of reach nearly everywhere ({present:.1%} of the areas above 0 < {MIN_TERM_PRESENCE:.0%})")
        else:
            alive.append(t)

    # b. redundant pairs: strongest terms first, a later term too close to a kept one is dropped
    ordered = sorted(alive, key=lambda t: (-abs(with_price[t]), t))
    corr = _weighted_corr(frame, [_col(t) for t in ordered]) if ordered else np.zeros((0, 0))
    kept = []
    for i, t in enumerate(ordered):
        twin = next((ordered[j] for j in range(i) if ordered[j] in kept and abs(corr[i, j]) >= REDUNDANT_CORR), None)
        if twin is None:
            kept.append(t)
        else:
            drop(t, f"redundant with {twin} (|r| = {abs(corr[i, ordered.index(twin)]):.2f} >= {REDUNDANT_CORR:g})")
            report[t]["redundant_with"] = twin

    # c. collinearity: highest VIF out, until every VIF is acceptable
    while len(kept) > 1:
        vif = variance_inflation(frame, kept)
        worst = max(kept, key=lambda t: (vif[t], -abs(with_price[t]), t))
        if vif[worst] <= VIF_MAX:
            break
        drop(worst, f"collinear with the other terms (VIF {vif[worst]:.1f} > {VIF_MAX:g})")
        kept.remove(worst)

    # d. too little influence: weakest violator out, refit, until none is left
    def influence(current):
        data = _with_forms(frame, "linear", current)
        res = _fit(_formula("linear", controls, fixed_effects, current), data, clustered)
        return {t: {"coef": float(res.params[_xcol(t)]), "se": float(res.bse[_xcol(t)]), "p": float(res.pvalues[_xcol(t)]),
                    "effect_per_sd": abs(float(res.params[_xcol(t)])) * sd[t]} for t in current}

    stats = {}
    while kept:
        stats = influence(kept)
        weak = [t for t in kept if not (stats[t]["p"] <= INFLUENCE_P) or stats[t]["effect_per_sd"] < MIN_EFFECT_PER_SD]
        if not weak:
            break
        worst = max(weak, key=lambda t: (stats[t]["p"] if stats[t]["p"] == stats[t]["p"] else 1.0, -stats[t]["effect_per_sd"], t))
        why = (f"not significant (p = {stats[worst]['p']:.2f} > {INFLUENCE_P:g})" if not stats[worst]["p"] <= INFLUENCE_P
               else f"negligible effect ({stats[worst]['effect_per_sd']:.2%} per sd < {MIN_EFFECT_PER_SD:.1%})")
        drop(worst, f"too little influence: {why}")
        report[worst].update({k: _num(v) for k, v in stats[worst].items()})
        kept.remove(worst)
    final_vif = variance_inflation(frame, kept) if kept else {}
    for t in kept:
        report[t].update({k: _num(v) for k, v in stats[t].items()})
        report[t]["vif"] = _num(final_vif[t], 3)
    return kept, report


def _prediction(frame, data, formula, coefficients, controls, terms, form, fixed_effects):
    """
    What a dwelling's price is computed from, the same for the whole city: intercept, term betas, control
    coefficients, the municipality effects, the controls' means in the fit (they stand in for a control a
    dwelling lacks) and the smearing factor. exp(ln price) of a log model is the median, not the mean, of the
    price: Duan's (1983) smearing factor, the dwelling-weighted mean of exp(residual), corrects it, so the model
    reproduces the WOZ level of the areas it was calibrated on. Residuals are on the log scale of the stored fit
    (OLS or spatial error).
    """
    import numpy as np
    import patsy

    y, x = patsy.dmatrices(formula, data, return_type="dataframe")
    beta = np.array([coefficients[_term_of(name) or name]["coef"] for name in x.columns])
    residual = y.iloc[:, 0].to_numpy() - x.to_numpy() @ beta
    weights = frame["weight"].to_numpy(dtype=float)
    cities = {}
    if fixed_effects:
        for city in sorted(frame["city"].unique()):
            cities[str(city)] = float(coefficients.get(f"C(city)[T.{city}]", {}).get("coef", 0.0))
    return {
        "form": form,
        "intercept": float(coefficients["Intercept"]["coef"]),
        "terms": {t: float(coefficients[t]["coef"]) for t in terms},
        "controls": {c: float(coefficients[c]["coef"]) for c in controls},
        "control_means": {c: float(np.average(frame[c].to_numpy(dtype=float), weights=weights)) for c in controls},
        "cities": cities,
        "smearing": float(np.average(np.exp(residual), weights=weights)),
        "observed_mean": float(np.average(np.exp(frame["lnPrice"].to_numpy(dtype=float)), weights=weights)),
    }


# ── the fit ────────────────────────────────────────────────────────

def fit_hedonic(rows, seed=MORAN_SEED, permutations=MORAN_PERMUTATIONS, use_controls=True, exploratory=False,
                cluster_name="neighborhood"):
    """
    Fit the model on `rows`, one dict per area: id, city, lnPrice, terms ({term: baseline value 0-100}), weight,
    x, y, geom (a shapely polygon) and the CONTROLS (None when missing). Returns the PriceModel fields as a dict
    (without wozYear / networkSnapshot / accessMethod, which the caller knows). Deterministic for given rows.

    `cluster_name` names what the rows' `cluster` key is (shown in the spec). `use_controls=False` fits the
    accessibility terms (and municipality effects) only. `exploratory=True` lowers the minimum to
    EXPLORATORY_MIN_AREAS to check the pipeline on a small area; the fit is marked in `spec` and `method` and is
    not interpretable (a handful of rows give wide, unstable betas).

    DAG edge: Accessibility -> Property
    """
    import pandas as pd

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise PriceModelError("No area has a WOZ value per m2 and a frozen accessibility baseline.")
    candidates = sorted({term for row in rows for term in (row.get("terms") or {})})
    if not candidates:
        raise PriceModelError("No area has a frozen accessibility baseline per amenity category.")
    for term in candidates:
        frame[_col(term)] = [(row.get("terms") or {}).get(term) for row in rows]
    for column in ("lnPrice", "weight", *CONTROLS, *[_col(t) for t in candidates]):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["lnPrice", "weight", *[_col(t) for t in candidates]])
    frame = frame[frame["weight"] > 0]
    controls = [c for c in CONTROLS if use_controls and c in frame and frame[c].notna().mean() >= MIN_CONTROL_COVERAGE
                and frame[c].nunique(dropna=True) > 1]
    dropped = [c for c in CONTROLS if c not in controls]
    frame = frame.dropna(subset=controls).reset_index(drop=True)
    minimum = EXPLORATORY_MIN_AREAS if exploratory else MIN_AREAS
    if len(frame) < minimum:
        raise PriceModelError(f"{len(frame)} areas have all the inputs; at least {minimum} are needed.")

    frame["city_code"] = pd.factorize(frame["city"])[0]
    cities = int(frame["city"].nunique())
    fixed_effects = cities >= MIN_CLUSTERS
    # errors are clustered by municipality; with one municipality by neighborhood when the rows carry one
    cluster_by = None
    if cities >= MIN_CLUSTERS:
        cluster_by, frame["cluster_code"] = "municipality", frame["city_code"]
    elif "cluster" in frame and frame["cluster"].nunique() >= MIN_CLUSTERS:
        cluster_by, frame["cluster_code"] = cluster_name, pd.factorize(frame["cluster"])[0]
    clustered = cluster_by is not None
    n_clusters = int(frame["cluster_code"].nunique()) if clustered else 0

    # 1. which terms: redundancy, collinearity and influence
    terms, screening = screen_terms(frame, candidates, controls, fixed_effects, clustered)
    if not terms:
        raise PriceModelError("No amenity category has a detectable association with the WOZ value per m2 after the "
                              "screening for redundancy and influence; see the screening report of a larger area.")
    parameters = len(terms) + len(controls) + 1 + (cities - 1 if fixed_effects else 0)
    if not exploratory and len(frame) < MIN_OBS_PER_PARAMETER * parameters:
        raise PriceModelError(f"{len(frame)} areas for {parameters} parameters ({len(terms)} terms, {len(controls)} controls, "
                              f"intercept and municipality effects): at least {MIN_OBS_PER_PARAMETER} per parameter are needed.")

    # 2. functional form
    folds = _folds(frame)
    comparison = {}
    for form in chain.PRICE_FORMS:
        res = _fit(_formula(form, controls, fixed_effects, terms), _with_forms(frame, form, terms), clustered)
        comparison[form] = {"aic": float(res.aic), "cv_r2": _cv_r2(frame, form, controls, terms, folds)}
    comparison["spline"] = {"aic": None, "cv_r2": _cv_r2(frame, "linear", controls, terms, folds, spline=True)}

    def rank(form):
        cv = comparison[form]["cv_r2"]
        return (cv if cv is not None else -math.inf, -comparison[form]["aic"])

    form = max(chain.PRICE_FORMS, key=rank)
    spline_cv, stored_cv = comparison["spline"]["cv_r2"], comparison[form]["cv_r2"]
    comparison["stored_form"] = form
    comparison["spline_departs"] = bool(spline_cv is not None and stored_cv is not None
                                        and spline_cv - stored_cv > SPLINE_FLAG_GAIN)
    comparison["blocks"] = "municipality" if cities >= CV_MIN_MUNICIPALITIES else f"{CV_GRID}x{CV_GRID} grid of centroids"

    # 3. the stored fit and its spatial diagnostic
    data = _with_forms(frame, form, terms)
    formula = _formula(form, controls, fixed_effects, terms)
    ols = _fit(formula, data, clustered)
    weights = spatial_weights(list(frame["geom"]))
    ols_i, ols_p = morans(ols.resid, weights, seed, permutations)
    chosen, coefficients, model_name, r2 = ols, _coefficients(ols), "ols", float(ols.rsquared)
    sem_i = sem_p = lam = None
    passed = ols_p >= MORAN_ALPHA
    if not passed:
        try:
            sem, sem_coefficients, lam, sem_r2 = _spatial_error(formula, data, weights, clustered)
            sem_i, sem_p = morans(sem.resid, weights, seed, permutations)
            if sem_p >= MORAN_ALPHA or abs(sem_i) < abs(ols_i):
                chosen, coefficients, model_name, r2 = sem, sem_coefficients, "sem", sem_r2
                passed = sem_p >= MORAN_ALPHA
        except Exception:   # noqa: BLE001 - the OLS result stands, flagged as not passing
            logger.warning("Spatial error model failed; the OLS betas are kept", exc_info=True)

    # 4. the same terms without the controls
    bare = _fit(_formula(form, [], fixed_effects, terms), data, clustered)
    bare_coefficients = _coefficients(bare)

    import importlib.metadata as metadata

    prediction = _prediction(frame, data, formula, coefficients, controls, terms, form, fixed_effects)
    for term in terms:   # the screening report keeps what the stored fit says about each kept term
        screening[term]["beta"] = coefficients[term]["coef"]
        screening[term]["beta_no_controls"] = bare_coefficients[term]["coef"]
    kept_set = set(terms)
    return {
        "design": "cross_section",
        "form": form,
        "n": int(len(frame)),
        "r2": r2,
        "coefficients": coefficients,
        "coefficientsNoControls": bare_coefficients,
        "termBetas": {term: coefficients[term]["coef"] for term in terms},
        "prediction": prediction,
        "screening": {"terms": screening, "candidates": len(candidates), "kept": len(terms),
                      "dropped": {t: v["reason"] for t, v in screening.items() if t not in kept_set},
                      "rules": {"min_sd": MIN_TERM_SD, "min_presence": MIN_TERM_PRESENCE, "redundant_corr": REDUNDANT_CORR,
                                "vif_max": VIF_MAX, "influence_p": INFLUENCE_P, "min_effect_per_sd": MIN_EFFECT_PER_SD}},
        "spatialModel": model_name,
        "moransI": ols_i, "moransP": ols_p, "moransISem": sem_i, "moransPSem": sem_p, "spatialLambda": lam,
        "diagnosticPassed": bool(passed),
        "permutations": permutations, "seed": seed,
        "formComparison": comparison,
        "spec": {
            "formula": formula, "weights": "dwellings", "terms": terms, "controls": controls, "dropped_controls": dropped,
            "municipalities": cities, "fixed_effects": fixed_effects,
            "errors": f"clustered by {cluster_by}" if clustered else "HC1 (one municipality)",
            "clusters": n_clusters,
            "r2_ols": float(ols.rsquared),
            "few_clusters": bool(clustered and n_clusters < FEW_CLUSTERS),
            "spatial_weights": "queen contiguity, row-standardised",
            "spatial_error": "lambda by ML (spreg.ML_Error, unweighted); coefficients by WLS on the filtered data",
            "alpha": MORAN_ALPHA,
            "exploratory": bool(exploratory), "controls_requested": bool(use_controls),
            "libraries": {name: metadata.version(name) for name in ("statsmodels", "libpysal", "esda", "spreg", "numpy", "pandas")},
        },
        "method": f"{chain.PRICE_METHOD}; {model_name}, {form}, {len(terms)} of {len(candidates)} terms"
                  f"{'; exploratory, not interpretable' if exploratory else ''}; {chain.PRICE_LABEL}"[:255],
    }


# ── database side ──────────────────────────────────────────────────

def latest_woz_year():
    """Newest postcode statistics year with PostcodePrice rows that have a value per m2 and frozen baselines; None without."""
    from housing.models import PostcodePrice

    return (PostcodePrice.objects.filter(woz_per_sqm__isnull=False, baselineAccessWalk__isnull=False,
                                         baselineAccessBike__isnull=False)
            .exclude(baselineCategories={})
            .order_by("-year").values_list("year", flat=True).first())


def area_coverage(woz_row):
    """
    Dwellings the mean area is taken over / the CBS dwelling stock of the area; None without both.
    The area comes from the BAG dwellings loaded in the database (PDOK import), so an area that the
    import extent only clipped has a mean area from a thin, possibly skewed slice of its dwellings. Above 1
    is fine (BAG is newer than the CBS stock and counts every dwelling object).
    """
    if not woz_row.dwellings or not woz_row.areaDwellings:
        return None
    return woz_row.areaDwellings / woz_row.dwellings


def split_by_coverage(woz_rows):
    """(kept rows, [{"id", "coverage", "area_dwellings", "dwellings"}]): rows under MIN_AREA_COVERAGE are left out of the fit."""
    kept, excluded = [], []
    for row in woz_rows:
        coverage = area_coverage(row)
        if coverage is not None and coverage >= MIN_AREA_COVERAGE:
            kept.append(row)
        else:
            excluded.append({"id": row.postcode6, "coverage": None if coverage is None else round(coverage, 3),
                             "area_dwellings": row.areaDwellings, "dwellings": row.dwellings})
    return kept, excluded


def build_rows(year):
    """
    (rows, kept price rows, excluded) for one statistics year, from the stored WOZ values, baselines and controls
    of the PC6 postcode areas (controls from the buildings, the CBS shares and the neighborhood's SES). Areas whose
    mean dwelling area covers less than MIN_AREA_COVERAGE of the CBS stock are excluded.
    """
    from administrative.models import City
    from shapely import wkt

    from housing.models import NeighborhoodSocialProfile, PostcodePrice

    from . import postcode_woz

    candidates = list(PostcodePrice.objects.filter(year=year, woz_per_sqm__isnull=False, geom__isnull=False)
                      .exclude(baselineCategories={}))
    price_rows, excluded = split_by_coverage(candidates)
    controls = postcode_woz.building_controls([r.postcode6 for r in price_rows])
    ses = dict(NeighborhoodSocialProfile.objects.filter(neighborhood_id__in={r.neighborhood_id for r in price_rows if r.neighborhood_id})
               .values_list("neighborhood_id", "socioEconomicStatus"))
    centres = {c.pk: c.geom.centroid for c in City.objects.filter(pk__in={r.city_id for r in price_rows if r.city_id})}
    rows = []
    for r in price_rows:
        if r.city_id not in centres or not r.dwellings:
            continue
        centroid = r.geom.centroid
        rows.append({
            "id": r.postcode6, "city": r.city_id, "cluster": r.neighborhood_id or r.postcode4, "lnPrice": math.log(r.woz_per_sqm),
            "terms": r.baselineCategories, "weight": r.dwellings,
            "x": centroid.x, "y": centroid.y, "geom": wkt.loads(r.geom.wkt),
            "ses": ses.get(r.neighborhood_id),
            "apartmentShare": None if r.multiFamilyShare_pct is None else r.multiFamilyShare_pct / 100.0,
            "rentalShare": None if r.rentalShare_pct is None else r.rentalShare_pct / 100.0,
            "distCentre_km": centroid.distance(centres[r.city_id]) / 1000.0,
            **controls.get(r.postcode6, {}),
        })
    return rows, price_rows, excluded


def fit_and_store(woz_year=None, activate=True, reprice=True, use_controls=True, exploratory=False):
    """
    Fit on `woz_year` (default: the newest year available), store a housing.PriceModel and, when `activate`, make
    it the fit in use and reprice every dwelling with it. An exploratory fit (`use_controls=False, exploratory=True`)
    is stored but never activated or applied. The PC6 postcode rows (housing.PostcodePrice) are written or
    refreshed first, baselines frozen once. Raises PriceModelError when the fit cannot be made.
    """
    from django.db import transaction

    from housing.models import PriceModel

    from . import postcode_woz, property_price

    try:
        postcode_woz.prepare(woz_year)
    except ValueError as exc:
        raise PriceModelError(str(exc)) from exc
    woz_year = woz_year or latest_woz_year()
    if woz_year is None:
        raise PriceModelError("No postcode area with a WOZ value and a frozen accessibility baseline: import the CBS postcode "
                              "areas (PC6) for the area and compute the network accessibility first.")
    rows, price_rows, excluded = build_rows(woz_year)
    try:
        result = fit_hedonic(rows, use_controls=use_controls, exploratory=exploratory, cluster_name="neighborhood")
    except PriceModelError as exc:
        if excluded:
            raise PriceModelError(f"{exc} {len(excluded)} areas were left out because the BAG dwellings loaded cover "
                                  f"under {MIN_AREA_COVERAGE:.0%} of their CBS stock: import the properties for the whole area.") from exc
        raise
    result["spec"]["excluded_low_coverage"] = excluded
    result["spec"]["min_area_coverage"] = MIN_AREA_COVERAGE
    activate = activate and not exploratory
    kept = {row["id"] for row in rows}
    used = [r for r in price_rows if r.postcode6 in kept]
    snapshots = [r.baselineSnapshot for r in used if r.baselineSnapshot]
    methods = Counter(r.baselineMethod for r in used if r.baselineMethod)
    result["spec"]["baseline_methods"] = dict(methods)
    with transaction.atomic():
        if activate:
            PriceModel.objects.filter(isActive=True).update(isActive=False)
        model = PriceModel.objects.create(
            wozYear=woz_year, networkSnapshot=max(snapshots) if snapshots else None,
            accessMethod=methods.most_common(1)[0][0] if methods else "", isActive=activate, **result)
    model.repriced = property_price.reprice(model=model) if activate and reprice else 0
    return model
