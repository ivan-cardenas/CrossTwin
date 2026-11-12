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
    ("Bbl", "Besluit bouwwerken leefomgeving (Bbl), in force since 1 January 2024; art. 4.163 lid 2 "
     "(≥ 55 % of a dwelling's usable area is verblijfsgebied), §4.3.10 daylight. https://wetten.overheid.nl",
     "builtup/calculations/regulations.py"),
    ("IPLO vrije indeelbaarheid", "Informatiepunt Leefomgeving, *Vrije indeelbaarheid: regels bij nieuwbouw*. "
     "https://iplo.nl/regelgeving/regels-voor-activiteiten/technische-bouwactiviteit/nieuwbouw/rijksregels/vrije-indeelbaarheid/",
     "builtup/calculations/regulations.py"),
    ("IPLO infoblad woning", "Informatiepunt Leefomgeving (2026), *Besluit bouwwerken leefomgeving en woning* "
     "(infoblad, February 2026): minimum 18 m² verblijfsgebied per dwelling. "
     "https://iplo.nl/publish/pages/228127/infoblad-besluit-bouwwerken-leefomgeving-en-woning_200223-februari-2026.pdf",
     "builtup/calculations/regulations.py"),
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
    ("NEH 630", "USDA NRCS, *National Engineering Handbook* Part 630 Hydrology (SCS curve number, hydrologic soil groups).",
     "physicalEnv/calculations/soil.py"),
    ("Eurostat DEGURBA 2021", "Eurostat (2021). *Applying the Degree of Urbanisation: a methodological manual*.",
     "builtup/calculations/degurba.py"),
]
