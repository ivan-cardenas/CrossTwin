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
            "Residential demand (m³/day) = population × {litres per person per day | 1 000}",
            "Demand (m³/day) = residential demand × 1.2  (small businesses, Vitens)",
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
        "how": "Summed from the recorded loss entries of the year. A leak counts in proportion to the share of its pipe's length inside the area; apparent losses are split by the area's share of connected users. ILI rates only the leaks against what is technically unavoidable for this network: its mains length, its connections and each city's average pressure (editable on the city's coverage record, 30 m by default). Apparent losses are not leaks and do not count in it.",
        "eq": [
            "NRW = real losses + apparent losses",
            "NRW share = {NRW (m³/day) | supply (m³/day)} × 100 %",
            "ILI = {CARL | UARL}",
            "UARL (L/day) = (18 × Lm + 0.8 × Nc + 25 × Lp) × P",
        ],
        "where": [
            ("CARL", "current annual real losses: the recorded leakage volume"),
            ("UARL", "unavoidable annual real losses (IWA): what even a well-run network of this size leaks"),
            ("Lm", "mains length (km)"),
            ("Nc", "service connections: dwellings within the service area"),
            ("Lp", "private pipe from the property boundary to the meter (km; 5 m per connection)"),
            ("P", "average operating pressure (m) of each city's network"),
        ],
        "note": "An ILI below about 2 is considered good; 1 means only unavoidable leakage is left. The UARL equation is meant for networks with at least 3000 connections, 20 connections per km and 25 m pressure; below that the ILI is indicative.",
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
        "how": "From the PET raster computed by the Thermal Comfort tool (SOLWEIG for the radiation, then the person's heat balance with pet-adjusted, including an urban heat island and wind at 1.2 m). The card shows the raster's mean, min and max over the area. PET and UTCI come from the same run: the Thermal Comfort run that covers most of the area, the latest hour among equal ones. The line below the gauge names the run, its hour and the share of the area it covers. PET holds for one person: the \"For\" line names the person set in the tool's Person pill (age, sex, body, activity, clothing); without a choice it is Höppe's reference person (35 y male, 75 kg, 1.75 m, 80 W activity, 0.9 clo).",
        "eq": [
            "Heat in = heat out:  M + R + C + E + S = 0",
            "Icl = Σ Iclu  (clothing insulation = sum of the garments, ASHRAE 55)",
            "PET = room temperature giving the same skin and core temperature",
        ],
        "where": [
            ("M", "the person's metabolic heat: activity (met) × body surface area"),
            ("Icl, Iclu", "insulation of the whole outfit and of each garment, in clo"),
            ("R", "radiation exchange, driven by mean radiant temperature (Tmrt)"),
            ("C, E", "convection and evaporation (sweat, breathing)"),
            ("S", "heat stored in the body"),
        ],
        "note": "Stress bands (°C): 18–23 comfortable, 29–35 slight, 35–41 moderate, ≥ 41 extreme heat stress. Gauge ceiling 41 °C.",
    },
    "heat.utci": {
        "title": "UTCI (Universal Thermal Climate Index)",
        "what": "The temperature of a reference environment (light wind, shade, 50 % humidity) that causes the same body response as the real conditions.",
        "how": "From the UTCI raster computed by the Thermal Comfort tool (SOLWEIG-GPU) with a polynomial fitted to a multi-node model of human thermoregulation. The card shows the raster's mean, min and max over the area. PET and UTCI come from the same run: the Thermal Comfort run that covers most of the area, the latest hour among equal ones. The line below the gauge names the run, its hour and the share of the area it covers.",
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
    "housing.living_alone": {
        "title": "Residents Living Alone",
        "what": "The share of the residents who live alone. It adapts the housing demand to the neighborhood's household mix.",
        "how": "The default comes from CBS Wijken en Buurten: one-person households (households x share of one-person households) over the inhabitants of the neighborhoods in the area. Where CBS has no value, the RIVM severe-loneliness share stands in as a proxy. Each resident living alone takes a whole home; the others fill homes at the persons per multi-person home of the municipality (CBS 86291NED). At the municipality's own share the demand equals residents / average persons per home. The one-person homes are housed first, so the other homes hold more than the average. The slider only changes the dashboard and saves nothing.",
        "eq": [
            "Persons per multi-person home = {population - one-person households | households - one-person households}",
            "Housing demand = residents living alone + {other residents | persons per multi-person home}",
        ],
        "note": "More residents living alone means more homes are needed for the same population.",
    },
    "housing.supply_coverage": {
        "title": "Housing Supply Coverage",
        "what": "The share of housing demand that the current stock meets.",
        "how": "For a city or province, supply is the CBS dwelling stock at the end of the year (table 86098NED). CBS publishes it per municipality only, so for a district or neighborhood supply is the number of mapped dwellings (BAG residential function) inside it. Only usable homes count: dwellings in vacant buildings and units below the minimum dwelling area (18 m²) are left out, at the share found among the mapped dwellings. Demand is population ÷ persons per home, adapted to the share of residents living alone, so it follows the population dock and both sliders.",
        "eq": [
            "Coverage = {usable homes | homes needed} × 100 %",
            "Homes needed = {population | persons per home} × household-mix factor",
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
        "how": "The rate starts at the year's mean new-business rate on loans for house purchase in the Netherlands (DNB MFI statistics), else the province's recorded credit-supply rate (national, the same for every area). The slider is a what-if: it recomputes the monthly payment of the average recorded loan over its average term (30 years without records) as an annuity. Nothing is written.",
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
        "what": "How house prices move over time, relative to 2019 (= 100), and where they could go to 2100 if the long-run pattern holds.",
        "how": "For the area shown, the index is its CBS mean WOZ value per m² (weighted by dwellings, at each CBS table year as published) divided by its 2019 value, so it reflects the area's own price history. After the area's last observed year it moves with the national CBS price index of existing own homes (table 85773ENG): first its observed years, then its extension, whose growth starts at the recent trend (least squares on the logarithm of the last 10 observed years) and fades towards the long-run average growth of the whole national series (1995–2025), halfway after 5 years. So the area is not extrapolated from its own few years, and the recent boom is not repeated for 75 years. Without WOZ values the national index itself is shown. The Long-run Price Growth slider changes the rate the national growth fades to. The year slider sets the scenario year of the whole map; the chart shows the 5 years around it.",
        "eq": [
            "Index = 100 × {value | value in 2019}",
            "Growth(k) = long-run + (recent − long-run) × 0.5^(k ÷ 5)",
            "Area index(year) = last area index × {national index (year) | national index (last area year)}",
            "YoY change = {this year − last year | last year} × 100 %",
        ],
        "where": [
            ("k", "years after the last observed year"),
            ("recent", "national annual growth of the last 10 observed years"),
            ("long-run", "average annual growth of the whole national series, or the slider"),
        ],
        "note": "An index of 120 means prices are 20 % above 2019. The extension follows the national index and is a trend continuation, not a forecast: it has no demand, income, interest-rate or affordability feedback, and the 5-year fade is a modelling assumption, not a measured value. Without a 2019 value the chart plots the WOZ value per m².",
    },
    "housing.hpi_long_run": {
        "title": "Long-run Price Growth",
        "what": "The yearly price growth the house price index extension settles at, a what-if.",
        "how": "It starts at the average annual growth of the whole national index (CBS, first to last year). The national extension begins at the recent 10-year trend and fades towards this rate, halfway after 5 years. Raise it for a market that keeps outgrowing history, lower it for a cooling one. The area follows the national curve, and so do the modelled prices. Nothing is written.",
        "eq": ["Growth(k) = long-run + (recent − long-run) × 0.5^(k ÷ 5)"],
        "note": "Constant growth of 5 % a year multiplies prices by about 40 in 75 years, so values far ahead are an illustration of the rate chosen, not a forecast.",
    },
    "housing.modelled_price": {
        "title": "Modelled Price",
        "what": "What the dwellings of the area would sell for per m², from one price equation for the whole city that is calibrated on the CBS WOZ values per postcode area and uses how reachable each kind of amenity is.",
        "how": "A hedonic fit on the PC6 postcode areas relates ln WOZ per m² to the access to each amenity category (supermarket, shop, pharmacy, GP, hospital, school, childcare, library, sport, bus stop, tram/metro stop, train station, park), on foot and by bicycle, with controls for construction year, apartment share, rental share, energy label, socio-economic status and distance to the municipal centre (the card lists each with the price change per step, e.g. +10 years of construction year), and municipality effects (weighted least squares, errors clustered by municipality or neighborhood). Before the fit every term is screened: terms that hardly vary, that repeat another term (|r| ≥ 0.9), that are collinear with the others (VIF > 10) or that have no detectable influence (not significant at 10 % or under 0.5 % of price per standard deviation) are left out, and the card lists each with its reason. The fit tests its residuals for spatial autocorrelation (Moran's I) and uses a spatial error model when they fail, and compares a linear and a logarithmic form. The same intercept, coefficients and municipality effects are then applied to every dwelling's own variables: the WOZ value of its area is what the model was calibrated on, not an input of its price. A dwelling without a stored accessibility keeps its stored value; a control a dwelling lacks is replaced by its mean in the fit.",
        "eq": [
            "Price = S × e^(a + Σ β × T(A) + Σ γ × z + μ)",
        ],
        "note": "Association-based scenario (upper bound), not a forecast. The coefficients come from a cross-section of postcode areas, so accessibility is credited with everything that goes with it (prestige, jobs, older housing), and WOZ lags the market. S is Duan's smearing factor, which makes the model reproduce the WOZ level it was calibrated on. Local differences the variables do not explain are not carried into the price. The observed price per m² is not touched. To read what one amenity does, add it with the Add amenity button: the scores around it and the modelled prices are recomputed.",
    },
    "housing.hpi_window": {
        "title": "Index Year",
        "what": "The year the House Price Index and the modelled prices refer to: the scenario year of the map.",
        "how": "Moving the slider sets the scenario year for the whole map, and moving the scenario moves the slider. The chart shows the 5 years around it; years after the last observed one are the trend extrapolation. Modelled prices are the stored price × the index of this year ÷ the index of the WOZ year the price model was fitted on.",
        "eq": ["Price(year) = stored price × {index (year) | index (WOZ year)}"],
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
        "how": "Averages across all recorded properties in the area. The modelled value and price are the means of the modelled price stored on the dwellings (the value is that price × the living area, else the gross area).",
        "eq": [
            "Modelled value = modelled price per m² × living area",
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
        "how": "Count of neighborhoods per stress level (HousingAffordability). Each level comes from the housing cost (rent and mortgage, weighted by the share of rental homes) as a share of median income, raised by 10 % per standard deviation of below-average socio-economic status (CBS). Median income is the average of the neighborhoods' median incomes for the year.",
        "eq": [
            "Burden = {12 × monthly housing cost | median annual income}",
            "Adjusted burden = burden × (1 + 0.10 × −status score)",
            "Low < 30 %, moderate 30–40 %, high ≥ 40 % of the adjusted burden",
        ],
        "note": "The 30 % and 40 % bands follow the common affordability rule and Eurostat's overburden threshold (on gross, not disposable, income). The 10 % per status point is an assumption still to be tested.",
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
    "builtup.accessibility": {
        "title": "Network Accessibility",
        "what": "How well the buildings of the unit reach everyday destinations (shops, health care, schools, transit stops, parks) along the street network, on foot and by bicycle.",
        "how": "For every building, the network distance to the nearest amenities of each category is measured on the OpenStreetMap walk or bike network (a building's own offset to the street included). Reach is measured in travel time, the same for both modes: an amenity counts fully within 5 minutes (400 m on foot; 1.25 km by bike) and fades to nothing at 15 minutes (1.2 km on foot; 3.75 km by bike), because a bike covers more distance in the same time. Categories are weighted (food, health, transit and parks most), and a second or third shop adds less than the first. The card shows the mean over the unit's buildings. A new amenity can only raise a score.",
        "eq": [
            "Value of a distance d = 1 if d ≤ D₀; = exp(−λ (d − D₀)) up to the cut-off; = 0 beyond",
            "Score = 100 × {Σ category weight × value of the category | Σ category weight}",
        ],
        "note": "Scores are relative to the destinations in OpenStreetMap, so they follow how completely it is mapped. A building more than 250 m from the network counts as not connected. The score is a connectivity measure, not a price: any link to property value is a separate, association-based estimate.",
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
    # ── Scenarios panel (weather/partials/climate_panel.html, mainMap climate partials) ──
    "climate.scenario": {
        "title": "KNMI'23 climate scenarios",
        "what": "How the Dutch climate may change by 2050 (2036-2065) or 2100 (2086-2115), compared with 1991-2020. Four pathways: low or high emissions, each with a dry and a wet variant. The quick picks are the three the Klimaateffectatlas viewer offers; its \"high\" is taken as High, dry (Hd), the heat and drought case. High, wet is the heavy-rain case.",
        "how": "KNMI's national-average changes per season (Table 1 of KNMI Publication 23-03) are added to the observed weather (delta change). Picking a scenario also sets the population year: 2025 for the current climate, else the horizon year. The table shows the change of every season; the highlighted column is the one the heat panel applies.",
        "eq": [
            "Scenario temperature = observed temperature + change",
            "Scenario rain = observed rain × (1 + {change (%) | 100})",
            "Scenario humidity = observed humidity + change (%-points)",
        ],
        "note": "A what-if: choosing a scenario writes nothing. The Urban Heat and Water Supply panels apply it until you pick Current. Summer extremes: KNMI's change of the 1-day rain that falls once per 10 years scales the Rain Event. Colours: red warmer, blue cooler; teal wetter, ochre drier. Source: KNMI'23 climate scenarios, knmi.nl/klimaatscenarios.",
    },
    "climate.interpolation": {
        "title": "Decades between 2050 and 2100",
        "what": "KNMI'23 publishes changes for 2050 (2036-2065) and 2100 (2086-2115) only. The decades 2030, 2040 and 2060-2090 are interpolated so you can explore the years in between; 2050 and 2100 are the published values.",
        "how": "Linear in time between three anchors: no change at 2005 (the middle of the 1991-2020 reference), the KNMI'23 change in 2050 and in 2100. The same weights apply to every season, indicator and station key figure. Click a point or a cell to pick that year and pathway; the population year follows it.",
        "eq": [
            "Change (year ≤ 2050) = change 2050 × {year − 2005 | 2050 − 2005}",
            "Change (year > 2050) = change 2050 + (change 2100 − change 2050) × {year − 2050 | 50}",
            "Added to observed weather = change (scenario year) − mean of the four pathways' change (observed year)",
        ],
        "note": "Not a KNMI product: the real path between the horizons follows global warming, which is not linear in time. The low-emission pathways stabilise after 2050, so their 2060-2100 values equal 2050. Weather observed today already holds part of the change since 1991-2020; the scenario adds only the part above the dashed line (the mean of the four pathways at the observed year, the same for every pathway), and nothing for a year at or before the observed one. Stored runs record both methods with the KNMI'23 source.",
    },
    "climate.heat_day": {
        "title": "Season / heat day",
        "what": "Which change is added to the observed weather when the heat panel and the effects table move it into the scenario.",
        "how": "Observed season adds the change of the season the observed weather falls in; a season button adds that season's change whatever the date (a stored run asks for a date in that season). Both use the change of the average daily maximum by day and the average daily minimum by night, which understates heat waves: the hottest days warm more. Warmest day of the year adds the change of the warmest day at the KNMI key-figure station nearest to the selected area (De Bilt, Den Helder, Groningen, Maastricht or Vlissingen); apply it to a hot observed day.",
        "eq": [
            "Day temperature = observed + change of the daily maximum",
            "Night temperature = observed + change of the daily minimum",
            "Heat-wave day = observed + change of the warmest day (nearest station)",
        ],
        "note": "Station key figures: klimaatscenarios-data.knmi.nl. The portal does not define the warmest day; its 1991-2020 values match the warmest daily mean temperature.",
    },
    "climate.effects": {
        "title": "Scenario effects",
        "what": "The selected area today (2025 population, observed weather) next to the chosen scenario (its horizon year's population, scenario weather).",
        "how": "Calculate effects stores a scenario run: the heat model (SOLWEIG: Tmrt, UTCI, PET, WBGT) over the map view on one observed hour moved into the scenario, water availability and demand, and the homes needed for the scenario population. Observed data stay unchanged. Quick what-if computes the weather-only heat stress (no shading or surfaces) and the water balance in the browser request and stores nothing.",
        "eq": [
            "Change = scenario value − current value",
            "WBGT = 0.7 × wet-bulb + 0.2 × globe + 0.1 × air temperature",
        ],
        "note": "Change colours: red = worse, teal = better, uncoloured = no judgement (population, humidity, wind). A strong colour marks a change of 10 % or more of today's value. LST is not projected (it depends on the surface reflectance a satellite measures); SUHII stays observed. Years past the CBS projection are a trend extrapolation (*).",
    },
    "climate.run_actions": {
        "title": "Update results or rerun the heat simulation",
        "what": "A stored run is a snapshot. Two buttons bring it up to date, depending on what changed.",
        "how": "Update results recomputes water, housing and the comparison from the data stored now, in seconds; it reuses the heat simulation already done (and picks up an observed Thermal Comfort run of the same hour for the current column). Rerun heat simulation runs SOLWEIG again on the GPU, which takes minutes; needed after buildings, land cover, soil or the DSM changed (the button turns amber then).",
        "eq": [
            "Update results: water + housing + current column, from stored data",
            "Rerun heat simulation: Tmrt, UTCI, PET, WBGT of the scenario hour",
        ],
        "note": "Delete removes the run and its scenario layers; a second click within 4 s confirms.",
    },
}
