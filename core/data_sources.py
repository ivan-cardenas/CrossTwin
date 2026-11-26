"""
Every external source CrossTwin reads, for docs/DATA_SOURCES.md
(written by tools/data_sources.py; core/tests/test_data_sources.py checks
the file is current).

The importer catalog (importer/external_catalog.py) lists its own datasets;
this module adds what is fetched elsewhere (map tools, weather, Earth Engine
inputs of calculations) and the regulations, standards and literature that
equations and checks cite. When code starts reading a new source or citing
a new rule, add it here and run `uv run python tools/data_sources.py`.
"""

# Sources read outside the importer catalog: (name, provider, endpoint/asset, used by, notes)
OTHER_SOURCES = [
    ("Current weather (map weather pill, heat what-if baseline)", "Open-Meteo",
     "https://api.open-meteo.com/v1/forecast (`current=`; `OPEN_METEO_URL`)",
     "weather/live.py::current_weather", "No key; cached per 0.02° cell for 10 min."),
    ("KNMI daily and hourly station data", "KNMI (Royal Netherlands Meteorological Institute)",
     "https://www.daggegevens.knmi.nl/klimatologie/daggegevens, .../uurgegevens",
     "weather/knmi.py (daily water balance), urban_heat/solweig/met.py (SOLWEIG met)",
     "RH, EV24, FG, TG, Q, UG (daily); hourly for the Thermal Comfort tool."),
    ("ERA5 hourly reanalysis", "ECMWF via Google Earth Engine", "ECMWF/ERA5/HOURLY",
     "urban_heat/solweig/met.py, urban_heat/lst/gee.py",
     "SOLWEIG meteorology; total column water vapour for LST after NCEP stopped (2026-03-18)."),
    ("ERA5-Land hourly / daily", "ECMWF via Google Earth Engine", "ECMWF/ERA5_LAND/HOURLY, ECMWF/ERA5_LAND/DAILY_AGGR",
     "importer catalog (gee_precipitation, gee_wind_speed)", "Raster imports."),
    ("Landsat 8/9 Collection 2 (TOA + Level 2 QA)", "USGS / NASA via Google Earth Engine",
     "LANDSAT/LC08/C02/T1_TOA, LANDSAT/LC09/C02/T1_TOA, LANDSAT/LC08/C02/T1_L2, LANDSAT/LC09/C02/T1_L2",
     "urban_heat/lst/gee.py", "B10 brightness temperature and QA_PIXEL cloud mask for the LST tool."),
    ("ASTER Global Emissivity Dataset", "NASA JPL via Google Earth Engine", "NASA/ASTER_GED/AG100_003",
     "urban_heat/lst/gee.py", "Bare-ground emissivity of the SMW algorithm."),
    ("NCEP/NCAR reanalysis water vapour", "NOAA via Google Earth Engine", "NCEP_RE/surface_wv",
     "urban_heat/lst/gee.py", "Total precipitable water for the SMW coefficients (until 2026-03-18)."),
    ("Copernicus Data Space (openEO, catalogue)", "ESA / Copernicus",
     "https://openeo.dataspace.copernicus.eu, https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
     "importer (sentinel2_* entries)", "Sentinel-2 L2A indices (NDVI, NDWI, moisture, albedo, true colour)."),
    ("CBS StatLine OData", "Statistics Netherlands (CBS)",
     "https://opendata.cbs.nl/ODataApi/OData/, https://opendata.cbs.nl/ODataFeed/OData/",
     "importer (CBS_* entries)", "Tables 86098NED, 86291NED, 85173NED and others."),
    ("CBS Kerncijfers wijken en buurten 2019-2024 (WOZ value per buurt)", "Statistics Netherlands (CBS)",
     "https://opendata.cbs.nl/ODataApi/OData/{84583NED,84799NED,85039NED,85318NED,85618NED,85984NED}/TypedDataSet",
     "importer/cbs_woz.py (CBS_WOZ_<year> entries) -> housing.WOZValue",
     "Mean WOZ value of the dwellings (x 1 000 EUR, valuation date 1 January of the year before) and the dwelling stock; "
     "no value below 20 dwellings. Column keys differ per table year."),
    ("NVM quarterly housing-market reports (PDF)", "NVM (Nederlandse Vereniging van Makelaars)",
     "https://www.nvm.nl/wonen/marktinformatie-wonen/ (PDFs read from `NVM_PDF_DIR`, not downloaded by CrossTwin)",
     "importer/nvm_reports.py (nvm_market_reports) -> housing.NVMMarketReport, NVMRegionMapping",
     "Median transaction price per m2 per region and quarter. NVM's copyright and disclaimer pages allow non-commercial "
     "private use only and reserve reproduction and redistribution (checked 2026-11-26; robots.txt allows the pages): "
     "get NVM's written permission before the figures are published or shared. Each row stores the PDF's SHA-256 and the parser version."),
    ("Overpass API (OpenStreetMap)", "OpenStreetMap contributors (ODbL)",
     "https://overpass-api.de/api/interpreter (`OVERPASS_URL`, mirrors in `OVERPASS_MIRRORS`)",
     "importer (osm_* entries)", "Parks, water bodies, amenities, trees."),
    ("BIJ12 Informatiekaart Natuur", "BIJ12 (joint provinces)",
     "https://ogc-geoservices.bij12.nl/geoserver/IMNa_IKN/wfs (`IMNa_IKN:natuur_netwerk_nederland`)",
     "importer (bij12_nnn) -> builtup/calculations/site.py",
     "Natuurnetwerk Nederland; the neighbourhood generator keeps buildings out of it."),
    ("Natura 2000 areas", "RVO via PDOK", "https://service.pdok.nl/rvo/natura2000/wfs/v1_0",
     "importer (pdok_natura2000) -> builtup/calculations/site.py", "Cut out of the generator's buildable area."),
    ("Basemap tiles", "Mapbox", "Mapbox GL JS styles (`MAPBOX_ACCESS_TOKEN`)", "mainMap (map rendering)",
     "Display only; no data is stored."),
]

# Regulations, standards and literature cited by checks and equations: (key, citation, used by)
REFERENCES = [
    ("Walk Score methodology", "Walk Score (2011), Walk Score Methodology: a walkability score from the distance to "
     "amenity categories, full value close by and a smooth decay to a cut-off, with diminishing weight on further "
     "amenities of one category.",
     "builtup/calculations/chain.py::distance_decay, accessibility_score (builtup.Accessibility)"),
    ("15-minute city catchments", "Moreno, C., Allam, Z., Chabaud, D., Gall, C. & Pratlong, F. (2021), Introducing the "
     "'15-Minute City': Sustainability, resilience and place identity in future post-pandemic cities, *Smart Cities* "
     "4(1), 93-111: daily needs within a 15 minute walk or bike ride. The walking and cycling catchments are v1 "
     "choices anchored on it, not estimates.",
     "builtup/calculations/chain.py::FULL_VALUE_M, CUTOFF_M, CATEGORIES (builtup.Accessibility)"),
    ("Vitens small business", "Vitens N.V., reports and calculations of the drinking-water company: "
     "small-business (kleinzakelijk) demand on top of household use, total demand = 1.2 x residential demand.",
     "watersupply/calculations/chain.py::SMALL_BUSINESS_DEMAND_FACTOR, demand_m3_d (TotalWaterDemand, "
     "ScenarioWaterSecurity, water dashboard)"),
    ("IWA UARL", "Lambert, A., Brown, T. G., Takizawa, M. & Weimer, D. (1999), A review of performance indicators "
     "for real losses from water supply systems, *J. Water Supply: Research and Technology-AQUA* 48(6), 227-237: "
     "UARL [L/day] = (18 Lm + 0.8 Nc + 25 Lp) x P, ILI = CARL / UARL (IWA Water Loss Task Force).",
     "watersupply/calculations/chain.py::uarl_m3_d, ili (LeakageIndex, water dashboard NRW card)"),
    ("UARL range", "Lambert, A. & McKenzie, R. (2002), Practical experience in using the Infrastructure Leakage Index, "
     "IWA Conference 'Leakage Management - A Practical Approach', Lemesos: the UARL equation holds for "
     ">= 3000 connections, >= 20 connections/km of mains and >= 25 m pressure.",
     "watersupply/calculations/chain.py::uarl_reliable"),
    ("KNMI'23", "KNMI (2023), *KNMI'23 climate scenarios for the Netherlands*, KNMI Publication 23-03, "
     "Table 1 (country averages, change relative to 1991-2020; Ld/Ln/Hd/Hn, 2050 and 2100). "
     "https://www.knmi.nl/klimaatscenarios — the Klimaateffectatlas viewer shows the current climate, 2050 high and 2100 high.",
     "weather/calculations/climate.py (Scenarios panel; heat and water what-ifs)"),
    ("KNMI'23 stations", "KNMI (2023), *KNMI'23 climate scenarios, key figures per station*, table Temperatuur "
     "(warmest day of the year, days with Tx >= 30 and >= 35 °C, tropical nights; De Bilt, Den Helder, Groningen, "
     "Maastricht, Vlissingen; change relative to 1991-2020). https://klimaatscenarios-data.knmi.nl, retrieved 2026-11-14.",
     "weather/calculations/climate.py (heat-wave day of the Scenarios panel)"),
    ("Bbl", "Besluit bouwwerken leefomgeving (Bbl), in force since 1 January 2024; art. 4.163 lid 2 "
     "(≥ 55 % of a dwelling's usable area is verblijfsgebied), §4.3.10 daylight. https://wetten.overheid.nl",
     "builtup/calculations/regulations.py"),
    ("IPLO vrije indeelbaarheid", "Informatiepunt Leefomgeving, *Vrije indeelbaarheid: regels bij nieuwbouw*. "
     "https://iplo.nl/regelgeving/regels-voor-activiteiten/technische-bouwactiviteit/nieuwbouw/rijksregels/vrije-indeelbaarheid/",
     "builtup/calculations/regulations.py"),
    ("IPLO infoblad woning", "Informatiepunt Leefomgeving (2026), *Besluit bouwwerken leefomgeving en woning* "
     "(infoblad, February 2026): minimum 18 m² verblijfsgebied per dwelling. "
     "https://iplo.nl/publish/pages/228127/infoblad-besluit-bouwwerken-leefomgeving-en-woning_200223-februari-2026.pdf",
     "builtup/calculations/regulations.py; housing/calculations/chain.py::MIN_DWELLING_AREA_SQM (usable homes of the housing supply)"),
    ("IPLO daglicht", "Informatiepunt Leefomgeving, *Daglichttoetreding: regels bij nieuwbouw* (NEN 2057). "
     "https://iplo.nl/regelgeving/regels-voor-activiteiten/technische-bouwactiviteit/nieuwbouw/rijksregels/daglichttoetreding/",
     "builtup/calculations/regulations.py"),
    ("IPLO brandcompartiment", "Informatiepunt Leefomgeving, *Brandcompartiment: regels bij nieuwbouw* (fire spread, NEN 6068). "
     "https://iplo.nl/regelgeving/regels-voor-activiteiten/technische-bouwactiviteit/nieuwbouw/rijksregels/brandcompartiment/",
     "builtup/calculations/regulations.py"),
    ("NEN 2580", "NEN 2580:2007, *Oppervlakten en inhouden van gebouwen*: usable area (GO) ≈ 0.8 × gross floor area "
     "(BVO), a typical ratio.", "builtup/calculations/regulations.py"),
    ("NEN 6068", "NEN 6068, *Bepaling van de weerstand tegen branddoorslag en brandoverslag tussen ruimten*: "
     "5 m between facades without fire-resistant walls.", "builtup/calculations/regulations.py"),
    ("Vanegas et al. 2012", "Vanegas, C.A., Kelly, T., Weber, B., Halatsch, J., Aliaga, D.G., Müller, P. (2012). "
     "Procedural generation of parcels in urban modeling. *Computer Graphics Forum* 31(2), 681–690.",
     "builtup/calculations/generative.py"),
    ("Parish & Müller 2001", "Parish, Y.I.H., Müller, P. (2001). Procedural modeling of cities. *SIGGRAPH 2001*, 301–308.",
     "builtup/calculations/generative.py (street patterns)"),
    ("Berghauser Pont & Haupt 2010", "Berghauser Pont, M., Haupt, P. (2010). *Spacematrix: Space, Density and Urban Form*. "
     "NAi Publishers.", "builtup/calculations/chain.py::layout_metrics (FSI, GSI)"),
    ("Natura 2000 / NNN law", "Omgevingswet and Besluit activiteiten leefomgeving (Natura 2000, formerly Wet "
     "natuurbescherming); provincial omgevingsverordening (Natuurnetwerk Nederland).",
     "builtup/calculations/site.py"),
    ("HILUCS", "INSPIRE Hierarchical INSPIRE Land Use Classification System. "
     "http://inspire.ec.europa.eu/codelist/HILUCSValue", "physicalEnv/hilucs.py, builtup/calculations/site.py"),
    ("CORINE", "European Environment Agency, *CORINE Land Cover nomenclature*. https://land.copernicus.eu/",
     "physicalEnv/calculations/landcover.py"),
    ("Oke et al. 2017", "Oke, T.R., Mills, G., Christen, A., Voogt, J.A. (2017). *Urban Climates*. Cambridge University Press "
     "(Table 5.1 albedo).", "physicalEnv.SurfaceMaterialProperties"),
    ("Bonafoni & Sekertekin 2020", "Bonafoni, S., Sekertekin, A. (2020). Albedo retrieval from Sentinel-2 by new "
     "narrow-to-broadband conversion coefficients. *IEEE GRSL* 17(9), 1618–1622.", "physicalEnv/calculations/albedo.py"),
    ("Ermida et al. 2020", "Ermida, S.L., Soares, P., Mantas, V., Göttsche, F.-M., Trigo, I.F. (2020). Google Earth Engine "
     "open-source code for land surface temperature estimation from the Landsat series. *Remote Sensing* 12(9), 1471. "
     "https://doi.org/10.3390/rs12091471", "urban_heat/lst/"),
    ("Koopmans et al. 2020", "Koopmans, S., Heusinkveld, B.G., Steeneveld, G.J. (2020). A standardized Physical Equivalent "
     "Temperature urban heat map at 1-m spatial resolution to facilitate climate stress tests in the Netherlands. "
     "*Building and Environment* 181, 106984.", "urban_heat/solweig/pipeline.py::urban_pet"),
    ("ASHRAE 55-2020", "ASHRAE (2020). *ANSI/ASHRAE Standard 55-2020: Thermal Environmental Conditions for Human "
     "Occupancy* (Table 5.2.1.2 metabolic rates, Table 5.2.2.2B garment insulation, Icl = sum of Iclu).",
     "urban_heat/calculations/person.py (Thermal Comfort tool's person pill, PET)"),
    ("ISO 7730:2005", "ISO 7730:2005, *Ergonomics of the thermal environment*, Annex C Table C.2 (insulation of "
     "outdoor garments).", "urban_heat/calculations/person.py::GARMENTS"),
    ("ISO 8996:2021", "ISO 8996:2021, *Ergonomics of the thermal environment: Determination of metabolic rate*.",
     "urban_heat/calculations/person.py::ACTIVITIES"),
    ("Höppe 1999", "Höppe, P. (1999). The physiological equivalent temperature: a universal index for the "
     "biometeorological assessment of the thermal environment. *Int. J. Biometeorology* 43, 71-75 (reference person).",
     "urban_heat/calculations/person.py::STANDARD_PERSON"),
    ("DuBois & DuBois 1916", "DuBois, D., DuBois, E.F. (1916). A formula to estimate the approximate surface area if "
     "height and weight be known. *Archives of Internal Medicine* 17, 863-871.",
     "urban_heat/calculations/person.py::body_surface_area"),
    ("NEH 630", "USDA NRCS, *National Engineering Handbook* Part 630 Hydrology (SCS curve number, hydrologic soil groups).",
     "physicalEnv/calculations/soil.py"),
    ("Eurostat housing cost overburden", "Eurostat, EU-SILC *housing cost overburden rate*: share of the population in "
     "households spending 40 % or more of disposable income on housing; with the common 30 % affordability rule of thumb "
     "it sets the moderate/high bands of the affordability stress level. The SES weight (10 % of the burden per SD of the "
     "CBS socio-economic status score) is a modelling assumption, not a cited coefficient.",
     "housing/calculations/chain.py::BURDEN_MODERATE, BURDEN_HIGH, SES_WEIGHT"),
    ("Eurostat DEGURBA 2021", "Eurostat (2021). *Applying the Degree of Urbanisation: a methodological manual*.",
     "builtup/calculations/degurba.py"),
]
