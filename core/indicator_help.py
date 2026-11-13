"""
Help texts behind the "?" buttons of the indicator dashboards and side panels.

One entry per card, keyed "<domain>.<card>", rendered by
``{% info_help "<key>" %}`` (core/templatetags/indicator_help.py) into the
button's hidden <template>, which core/static/js/info_popover.js shows.

Each entry:
    title  card name shown as the popover heading
    what   what the indicator is, in plain words
    how    how CrossTwin measures it (data source, aggregation)
    eq     equations, written for people: words over symbols. Write a
           fraction as ``{numerator | denominator}``; it renders stacked.
    where  optional (symbol, meaning) pairs explaining the equation's terms
    note   optional caveat, threshold or reading guide

Keep the equations in step with the code they describe (watersupply/calculations/chain.py,
urban_heat/calculations/chain.py, housing/calculations/chain.py, the apps' views/calculations); the
docstring next to each equation in the code is the reference.
"""

HELP = {
    # ── Water supply ───────────────────────────────────────────────────
    "water.supply_demand": {
        "title": "Supply vs Demand",
        "what": "How much drinking water is available to the area each year compared with how much its population uses.",
        "how": "Supply is the area's population share of the active wells' extraction in each watershed (measured yearly extraction, else pump flow × operating hours) plus imported water. Demand follows the population dock and the consumption slider. Both bars share one scale, the larger of the two, so their lengths compare directly.",
        "eq": [
            "Demand (m³/day) = population × {litres per person per day | 1 000}",
            "Supply (m³/day) = Σ watershed extraction × {area population | watershed population} + imported water",
            "Balance (Mm³/yr) = (supply − demand) × {365 | 1 000 000}",
        ],
        "note": "A positive balance is a surplus; a negative one is a shortfall.",
    },
    "water.supply_security": {
        "title": "Supply Security",
        "what": "Whether production covers demand, as a percentage.",
        "how": "Yearly supply and demand from the Supply vs Demand card. The stored value uses the CBS median population forecast of the year; the dashboard reruns the same equation with the what-if controls.",
        "eq": ["Supply security = {supply (m³/day) | demand (m³/day)} × 100 %"],
        "note": "Above 100 % production covers demand with a surplus; below 100 % there is a shortfall.",
    },
    "water.service_time": {
        "title": "Service Time",
        "what": "Hours per day the network can realistically deliver water.",
        "how": "Derived from supply security: when supply falls short, water is rationed over fewer hours.",
        "eq": [
            "If supply ≥ demand:  service time = 24 h",
            "Otherwise:  service time = 24 h × {supply | demand}",
        ],
        "note": "Continuous supply (24 h) is the target.",
    },
    "water.opex": {
        "title": "OPEX",
        "what": "Estimated yearly operating cost of producing the area's water.",
        "how": "Yearly supply volume multiplied by the average operating cost per m³ over all active extraction wells (energy, chemicals, staff). The bar compares it with a fixed reference budget of €10 000 000 a year.",
        "eq": ["OPEX (€/yr) = supply (m³/day) × 365 × average cost (€/m³)"],
    },
    "water.nrw": {
        "title": "Non-Revenue Water (NRW)",
        "what": "Water that is produced but never billed: lost through leaks (real losses) or through theft and meter errors (apparent losses).",
        "how": "Summed from the recorded loss entries of the year. A leak counts in proportion to the share of its pipe's length inside the area; apparent losses are split by the area's share of connected users. ILI rates only the leaks against what is technically unavoidable.",
        "eq": [
            "NRW = real losses + apparent losses",
            "NRW share = {NRW (m³/day) | supply (m³/day)} × 100 %",
            "ILI = {CARL | UARL}",
        ],
        "where": [
            ("CARL", "current annual real losses: the recorded leakage volume"),
            ("UARL", "unavoidable annual real losses: each leak × its unavoidable share"),
        ],
        "note": "An ILI below about 2 is considered good; 1 means only unavoidable leakage is left.",
    },
    "water.coverage": {
        "title": "Network Coverage",
        "what": "Main value: the share of water users (the residents of each home) living within reach of a pipe. Below it, the urban area the pipe network has not followed yet: where the network should be extended.",
        "how": "The pipes are buffered by the city's service distance (50 m unless the coverage record sets another). A home is served when it lies inside that buffer. The urban area is the city's built-up land cover (urban fabric, roads, rail, transport) of the latest land-cover year; the part of it outside the buffer is reported. It updates when pipes, homes, residents or land cover change.",
        "eq": [
            "Coverage = {residents within the buffer | all residents} × 100 %",
            "Urban area without network = urban land cover − (urban land cover ∩ service area)",
            "Share = {urban area without network | urban land cover} × 100 %",
        ],
        "where": [
            ("service area", "the pipes buffered by the service distance, merged"),
        ],
        "note": "The network itself is not extended automatically; the figure flags where it lags behind urban growth. The map's water-drop markers show the homes outside the buffer.",
    },
    "water.recharge": {
        "title": "Groundwater Recharge & Infiltration",
        "what": "Main value: the rain that neither runs off nor evaporates and so reaches the groundwater in a year. The same equation gives each fresh-water source its stored yield.",
        "how": "The area is cut into soil × land-cover pieces. Each piece gets a curve number (CN) from its hydrologic soil group (A sand … D clay/peat; also D on undrained land where groundwater is within 60 cm) and its land-cover class. Runoff is computed per day and piece with the SCS Curve Number method (USDA TR-55) over the latest complete year of daily KNMI rain; evaporation is the Makkink reference ET of the nearest station.",
        "eq": [
            "Recharge = rain − runoff − evapotranspiration  (never below 0)",
            "Runoff Q = {(P − 0.2 S)² | P + 0.8 S}  when P > 0.2 S, else 0",
            "Retention S (mm) = {25 400 | CN} − 254",
        ],
        "where": [
            ("P", "rain of the day or event (mm)"),
            ("CN", "curve number, 30 (very permeable) to 100 (sealed or water)"),
        ],
        "note": "Simplifications: crop factor 1 for every surface and no soil-moisture store between days. The Rain Event row applies the runoff equation to a single event set with the Rain Event slider.",
    },
    "water.rain_event": {
        "title": "Rain Event",
        "what": "Rain depth of one storm, used by the infiltration row of the Groundwater Recharge card.",
        "how": "Runoff is computed per soil × land-cover piece with the SCS Curve Number method and summed by area; the rest soaks in.",
        "eq": [
            "Runoff Q = {(P − 0.2 S)² | P + 0.8 S}",
            "Infiltrated share = {P − Q | P} × 100 %",
        ],
        "note": "Heavier events run off a larger share: the soil's retention S is used up first.",
    },
    "water.gw_season": {
        "title": "Groundwater Season",
        "what": "Which groundwater level decides where the soil is waterlogged.",
        "how": "Wet = GHG, the mean highest groundwater level (winter); dry = GLG, the mean lowest (summer), both from BIS Nederland. Where it is within 60 cm of the surface, undrained land counts as soil group D (NEH 630), which lets the least water in.",
        "eq": ["Groundwater depth < 60 cm on undrained land  →  soil group D"],
        "note": "Built-up and paved land is drained, so it keeps its texture group. BIS has no groundwater values for most of it, nor for water bodies, whose curve number is 100 anyway.",
    },

    # ── Urban heat ─────────────────────────────────────────────────────
    "heat.weather": {
        "title": "Weather & Heat Stress",
        "what": "Current conditions in the area and how hot they feel to a person in the shade and in the sun.",
        "how": "Live values from Open-Meteo at a point of the area (a model nowcast, refreshed every 15 minutes), or the latest stored station reading. Moving the weather sliders turns this into a what-if: the estimates are recomputed from the weather alone and nothing is stored. The PET/UTCI rasters are not recomputed; run the Thermal Comfort tool for those.",
        "eq": [
            "Vapour pressure e (hPa) = {RH | 100} × 6.105 × exp({17.27 Ta | 237.7 + Ta})",
            "Feels-like (shade) = Ta + 0.348 e − 0.70 v − 4.25",
            "Feels-like (sun) = shade value + {0.70 Q | v + 10}",
            "WBGT estimate = 0.567 Ta + 0.393 e + 3.94",
        ],
        "where": [
            ("Ta", "air temperature (°C)"),
            ("RH", "relative humidity (%)"),
            ("v", "wind speed (m/s)"),
            ("Q", "sunlight absorbed by a standing person = 0.7 × 0.25 × solar radiation (W/m²)"),
        ],
        "note": "Feels-like is Steadman's apparent temperature (Australian Bureau of Meteorology form); the WBGT estimate is the BoM approximation, without wind or sun.",
    },
    "heat.lst": {
        "title": "Land Surface Temperature (LST)",
        "what": "How hot the ground, roofs and roads themselves are, as seen by a satellite. Surfaces can be far hotter than the air above them.",
        "how": "Computed by the map's LST tool from Landsat 8/9 thermal band 10 with the Statistical Mono-Window algorithm (Ermida et al. 2020). Vegetation (NDVI) sets each pixel's emissivity, atmospheric water vapour comes from NCEP or ERA5. The card shows the mean, min and max of the latest LST raster clipped to the area.",
        "eq": [
            "LST = A × {Tb | ε} + {B | ε} + C",
            "ε = vegetation share × ε(veg) + (1 − vegetation share) × ε(bare soil)",
        ],
        "where": [
            ("Tb", "brightness temperature measured by the satellite"),
            ("ε", "surface emissivity, from NDVI and ASTER GED"),
            ("A, B, C", "coefficients fitted for the day's water vapour"),
        ],
        "note": "The gauge is scaled against a 50 °C display ceiling.",
    },
    "heat.pet": {
        "title": "PET (Physiological Equivalent Temperature)",
        "what": "The air temperature of a standard indoor room at which a person would feel the same heat load as outdoors here. It folds sun, wind and humidity into one °C value.",
        "how": "From the latest PET raster, computed by the Thermal Comfort tool (SOLWEIG for the radiation, then the person's heat balance with pet-adjusted, including an urban heat island and wind at 1.2 m). The card shows the raster's mean, min and max over the area.",
        "eq": [
            "Heat in = heat out:  M + R + C + E + S = 0",
            "PET = room temperature giving the same skin and core temperature",
        ],
        "where": [
            ("M", "metabolic heat of a walking person"),
            ("R", "radiation exchange, driven by mean radiant temperature (Tmrt)"),
            ("C, E", "convection and evaporation (sweat, breathing)"),
            ("S", "heat stored in the body"),
        ],
        "note": "Stress bands (°C): 18–23 comfortable, 29–35 slight, 35–41 moderate, ≥ 41 extreme heat stress. Gauge ceiling 41 °C.",
    },
    "heat.utci": {
        "title": "UTCI (Universal Thermal Climate Index)",
        "what": "The temperature of a reference environment (light wind, shade, 50 % humidity) that causes the same body response as the real conditions.",
        "how": "From the latest UTCI raster, computed by the Thermal Comfort tool (SOLWEIG-GPU) with a polynomial fitted to a multi-node model of human thermoregulation. The card shows the raster's mean, min and max over the area.",
        "eq": ["UTCI = Ta + offset(Ta, Tmrt − Ta, wind, vapour pressure)"],
        "where": [
            ("Ta", "air temperature"),
            ("Tmrt", "mean radiant temperature: the heat a person receives from sun and surfaces"),
        ],
        "note": "Stress bands (°C): 9–26 none, 26–32 moderate, 32–38 strong, 38–46 very strong, ≥ 46 extreme heat stress.",
    },
    "heat.wbgt": {
        "title": "WBGT (Wet Bulb Globe Temperature)",
        "what": "The heat-stress measure used for work and sport: it combines air temperature, humidity, wind and sunshine.",
        "how": "From the latest WBGT raster imported from the KNMI Data Platform, as the mean over the area.",
        "eq": ["WBGT = 0.7 × wet-bulb + 0.2 × black-globe + 0.1 × air temperature"],
        "note": "Categories use provisional bands at 25 / 28 / 30 / 33 °C; the gauge is scaled against 35 °C.",
    },
    "heat.svf": {
        "title": "Sky View Factor (SVF)",
        "what": "The fraction of the sky visible from a point on the ground: 1 in an open field, close to 0 in a narrow alley.",
        "how": "Computed by the map's SVF tool from the surface model (DSM): around every cell it searches the horizon in many directions up to a set radius. The card shows the latest SVF raster's mean over the area, as a percentage.",
        "eq": ["SVF = average over directions of (1 − sin(horizon angle))"],
        "note": "Low SVF keeps streets shaded by day but traps heat at night, because surfaces cannot radiate it back to the sky.",
    },
    "heat.vegetation": {
        "title": "Vegetation Coverage",
        "what": "The share of the area that is green: parks plus green land cover (forest, grass, trees, nature).",
        "how": "Park space (parks and recreation areas such as sports fields and playgrounds) and the green land-cover classes of each city's most recent land-cover year are clipped to the unit (a polygon crossing the boundary counts only with its part inside), then merged into one shape before measuring, so ground covered by both a park and green land cover counts once.",
        "eq": [
            "Green area = area of (parks ∪ green land cover) inside the unit",
            "Vegetation coverage = {green area | unit area} × 100 %",
            "Green land cover outside parks = green area − park area",
        ],
        "note": "The slider only changes this displayed value; it does not yet recalculate LST/PET/UTCI.",
    },
    "heat.morphology": {
        "title": "Urban Morphology",
        "what": "Building and street statistics that describe the street canyons, which shape how heat and wind behave.",
        "how": "Each street has a stored canyon (Street Canyons layer), refreshed when the street or a building near it changes. Its height H is the mean of the building heights on the left and on the right within 30 m of the street, and an open side counts as 0. Its width W is the street width when one is typed in, else the distance between the nearest facades on both sides, else a default for the street class. The area value weights each street by its length inside the area. Without stored canyons it shows the proxy average height / average street width.",
        "eq": [
            "H = {H left + H right | 2}",
            "Street H/W = {H | W}",
            "Area H/W = {Σ (H/W × street length) | Σ street length}",
        ],
        "note": "Higher ratios mean narrower, more enclosed canyons that trap more heat. As a rule of thumb (Oke): below 0.5 is an open street, around 1 a regular canyon, above 2 a deep one.",
    },
    "heat.suhii": {
        "title": "Surface Urban Heat Island (SUHII)",
        "what": "How many °C hotter the city's surface is than its rural surroundings.",
        "how": "Mean, min and max of the latest SUHII raster clipped to the area.",
        "eq": ["SUHII = LST(urban) − LST(rural reference)"],
    },
    "heat.nbs": {
        "title": "Nature-Based Solutions (NBS)",
        "what": "Interventions that use nature to cool the city and hold rain: green roofs, bioswales, pocket parks, trees.",
        "how": "Count of the recorded NBS polygons and points inside the area, and the total area of the polygons.",
        "eq": ["NBS count = polygons + points", "NBS area = Σ polygon area"],
        "note": "This tracks the response in place; it is not yet linked to a measured cooling effect on PET/UTCI.",
    },

    # ── Housing ────────────────────────────────────────────────────────
    "housing.household_size": {
        "title": "Average Persons per Home",
        "what": "How many residents live in an occupied home on average.",
        "how": "The default is the CBS figure for the area: population forecast divided by private households on 1 January. Housing demand uses it, and every dwelling on the map is assumed to hold this many residents. Dragging the slider recalculates demand and coverage without saving anything.",
        "eq": [
            "Persons per home = {population | private households}",
            "Housing demand = {population | persons per home}",
        ],
        "note": "Fewer persons per home means more homes are needed for the same population.",
    },
    "housing.supply_coverage": {
        "title": "Housing Supply Coverage",
        "what": "The share of housing demand that the current stock meets.",
        "how": "Supply is the CBS housing stock. Demand is population ÷ persons per home, so it follows the population dock and the slider.",
        "eq": [
            "Coverage = {homes available | homes needed} × 100 %",
            "Homes needed = {population | persons per home}",
        ],
        "note": "Below 100 % there are not enough homes for the estimated demand.",
    },
    "housing.affordability": {
        "title": "Affordability (Price-to-Income)",
        "what": "How many years of income it takes to buy the median home.",
        "how": "Per neighborhood from its recorded median house price and median income, then averaged over the reporting neighborhoods. The badge shows the yearly mortgage cost as a share of income.",
        "eq": [
            "Price-to-income = {median house price | median income}",
            "Cost burden = {monthly mortgage payment × 12 | median income} × 100 %",
        ],
        "note": "≤ 3× is comfortable, 3–5× stretched, above 5× stressed.",
    },
    "housing.mortgage": {
        "title": "Average Fixed Mortgage Rate",
        "what": "The typical interest rate homebuyers in the area pay, and what that means per month.",
        "how": "Average rate from the credit-supply data, with the average monthly payment and loan amount of the recorded mortgages.",
        "eq": ["Monthly payment = L × {r | 1 − (1 + r)^(−n)}"],
        "where": [
            ("L", "loan amount"),
            ("r", "monthly interest rate = yearly rate ÷ 12"),
            ("n", "number of monthly payments"),
        ],
        "note": "The equation is the standard annuity mortgage; payments are read from the recorded mortgages.",
    },
    "housing.hpi": {
        "title": "House Price Index",
        "what": "How house prices move over time, relative to a base year set to 100.",
        "how": "Average index value over the reporting neighborhoods for the year; year-on-year change compares it with last year's average for the same neighborhoods.",
        "eq": ["YoY change = {this year − last year | last year} × 100 %"],
        "note": "An index of 120 means prices are 20 % above the base year.",
    },
    "housing.new_units": {
        "title": "New Housing Units",
        "what": "Homes recently completed and still in the pipeline, against the remaining shortage.",
        "how": "Completed units are projects with an expected completion year at or before the selected year; pipeline units are still ahead. Land take intersects the pipeline footprints with the latest land cover: greenfield is land not yet urban, infill is land already urban fabric, road, rail or transport.",
        "eq": [
            "Supply deficit = homes needed − homes available",
            "Deficit share = {deficit | homes needed} × 100 %",
        ],
    },
    "housing.property": {
        "title": "Property Market",
        "what": "What homes in the area sell and list for, and how many buildings stand empty.",
        "how": "Averages across all recorded properties in the area.",
        "eq": [
            "Price per m² = {sale price | living area}",
            "Vacancy = {vacant buildings | all buildings} × 100 %",
        ],
    },
    "housing.rental": {
        "title": "Rental Market",
        "what": "Average rent in the area and whether renting or buying is the cheaper option.",
        "how": "Average monthly rent across recorded rental listings; each listing's price-to-rent ratio uses its property's sale (else listing) price.",
        "eq": ["Price-to-rent = {sale price | monthly rent × 12}"],
        "note": "Higher ratios favour renting: buying costs many years of rent.",
    },
    "housing.stress": {
        "title": "Affordability Stress",
        "what": "How many neighborhoods are under low, moderate or high housing-cost stress.",
        "how": "Count of neighborhoods per recorded stress level (HousingAffordability). Median income is the average of the neighborhoods' median incomes for the year.",
        "eq": ["Disposable income = median income − median expenditure"],
        "note": "The stress thresholds are still to be validated against the literature.",
    },
    "housing.zoning": {
        "title": "Zoning & Land Value",
        "what": "How the zoned land is divided between living, working and mixed uses.",
        "how": "Zoned area per INSPIRE HILUCS land-use group from the ZoningArea records: residential (5, except 5.2), commercial (3.1, 3.2), industrial (2) and mixed use (5.2). The benchmark is the average recorded price per m² of residential zones.",
        "eq": ["Share of a use = {zoned area of that use | total zoned area} × 100 %"],
    },

    # ── Built-up fabric ────────────────────────────────────────────────
    "builtup.coverage": {
        "title": "Built-up Coverage",
        "what": "How much of the ground is covered by buildings, and how much floor space is stacked on it.",
        "how": "Building footprints (BAG) inside the unit. Storeys are the recorded floor count, else height ÷ 3 m.",
        "eq": [
            "Coverage = {Σ building footprints | unit area} × 100 %",
            "Floor-area ratio (FAR) = {Σ footprint × storeys | unit area}",
        ],
        "note": "A FAR of 1 means as much floor space as land, e.g. a whole plot with one storey or half of it with two.",
    },
    "builtup.park": {
        "title": "Park Area per Inhabitant",
        "what": "How much public park space each resident has.",
        "how": "Park space in the unit (parks plus recreation areas: sports fields, playgrounds; overlapping areas merged so ground counts once) plus the slider's additional hectares, divided by the projected population for the selected year.",
        "eq": ["Park area per inhabitant = {park area (m²) + added area | population}"],
        "note": "WHO Europe recommends at least 9 m² of green space per inhabitant, ideally 50 m². The tag shows below minimum, between, or at the ideal.",
    },
    "builtup.stock": {
        "title": "Building Stock",
        "what": "The number and size of buildings in the area, and how many homes they hold per resident.",
        "how": "Buildings (BAG panden) whose neighborhood lies in the unit. Units are the recorded housing and commercial units; height and floors are averages over the buildings that report them.",
        "eq": [
            "Dwellings per 1 000 = {units | population} × 1 000",
            "Vacancy = {vacant buildings | all buildings} × 100 %",
        ],
    },
    "builtup.mix": {
        "title": "Building Type Mix",
        "what": "What the buildings are used for: residential, commercial, industrial, public and so on.",
        "how": "Each building's coarse type comes from its BAG usage function(s) (gebruiksdoel). A building with functions of more than one type counts as Mixed; buildings without a recorded function show as Unknown. Colours match the Buildings layer on the map.",
        "eq": ["Share of a type = {buildings of that type | all buildings} × 100 %"],
    },
    "builtup.calculations.degurba": {
        "title": "Degree of Urbanisation",
        "what": "How urban the unit is by the GHSL / Eurostat Degree of Urbanisation: city, town (dense, semi-dense, suburban) or rural (village, dispersed, mostly uninhabited), and how fast its urban area grows.",
        "how": "Each neighborhood's population is shared equally over its residential properties (dwellings, never buildings), summed per 100 m cell and classified with the GHSL rules. At 100 m, density uses a 300 m window over settlement land only, so edge cells next to fields keep their density. The 1 km figure is the original method on the same data. The unit's class follows where most of its people live. The population dock's scenario reclassifies the whole grid in memory as a what-if.",
        "eq": [
            "Person share of a dwelling = {neighborhood population | dwellings in the neighborhood}",
            "Cell density = {people in the 3 × 3 window | settlement land of the window (km²)}",
            "City if {people in urban centres | people} ≥ 50 %; town if {people in centres + clusters | people} ≥ 50 %",
            "Rate = ({urban area now | urban area in the first year})^(1 / years) − 1",
        ],
        "note": "Urban centre: ≥ 1 500 inh./km² (or ≥ 50 % built-up), 4-connected, ≥ 50 000 people. Urban cluster: ≥ 300 inh./km², 8-connected, ≥ 5 000 people. GHSL's own grid can be imported as a reference layer; it is never used in these numbers. Method: docs/DEGREE_OF_URBANISATION.md.",
    },
    "builtup.age": {
        "title": "Construction Period",
        "what": "When the buildings were built, grouped in the periods of the Dutch housing-stock typology (RVO reference dwellings).",
        "how": "Buildings with a recorded construction year, counted per period.",
        "eq": ["Share of a period = {buildings built in that period | buildings with a year} × 100 %"],
        "note": "Each period shares building regulations, so it is a rough proxy for insulation level and renovation need.",
    },
    "builtup.streets": {
        "title": "Street Network",
        "what": "How much street there is and how densely it covers the area.",
        "how": "Street length clipped to the unit's boundary: a street crossing it counts only with its inside part. The split shows primary, secondary and residential streets by length.",
        "eq": ["Street density = {street length (km) | unit area (km²)}"],
    },
    "builtup.facilities": {
        "title": "Urban Facilities",
        "what": "Schools, hospitals, fire and police stations, markets and transport nodes serving the area.",
        "how": "Facilities in the unit's neighborhoods, set against the projected population for the selected year.",
        "eq": ["Facilities per 10 000 = {facilities | population} × 10 000"],
    },
}
