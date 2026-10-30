from datetime import date

from django.conf import settings

coordinate_system = settings.COORDINATE_SYSTEM


# Klimaateffectatlas (KEA) helpers, see the kea_* entries below and
# docs/KEA_WFS_MAPPING.md.
KEA_WFS_URL = "https://cas.cloud.sogelink.com/public/data/org/gws/YWFMLMWERURF/kea_public/wfs"
KEA_NODATA = [-99995, -99996, -99997, -99998, -99999]   # RIVM health monitor "no value" codes


def _kea_neighborhood(code_prop, fields, **directives):
    """Mapping for a per-buurt KEA layer: one row per stored neighborhood, keyed on its CBS code."""
    return {
        "__geometry__": "geom",
        "__unique__": code_prop,
        "__unique_field__": "neighborhood_id",
        "__require_existing__": {"property": code_prop, "model": "administrative.Neighborhood"},
        code_prop: "neighborhood_id",
        **fields,
        **directives,
    }


def _kea_building(id_prop, fields, **directives):
    """Mapping for a per-pand KEA layer: attributes written onto existing BAG buildings only."""
    return {
        "__geometry__": "geom",
        "__unique__": id_prop,
        "__unique_field__": "id",
        "__enrich__": True,
        "__require_existing__": {"property": id_prop, "model": "builtup.Building"},
        **fields,
        **directives,
    }



# ---------------------------------------------------------------------------
# Field Mapping Definitions
# ---------------------------------------------------------------------------
# These define how WFS properties map to Django model fields.
# Keys are WFS property names, values are model field names.
# Special keys:
#   "__geometry__" → the geometry field name in the model
#   "__unique__"   → the WFS property used for update_or_create lookup
#   "__static__"   → dict of {model_field: constant_value} applied to every
#                    feature in this dataset, regardless of WFS properties

FIELD_MAPPINGS = {
    "pdok_provinces": {
        "__geometry__": "geom",
        "__unique__": "naam",
        "__unique_field__": "ProvinceName",
        "naam": "ProvinceName",
        "code": "id",
        # Population fields are computed in model.save(), not from WFS
    },
    "pdok_cities": {
        "__geometry__": "geom",
        "__unique__": "naam",
        "__unique_field__": "cityName",
        "__spatial_fk__": {"field": "province", "model": "administrative.Province", "required": True},
        "naam": "cityName",
        "code": "id",
    },
    "pdok_districts": {
        "__geometry__": "geom",
        "__unique__": "wijkcode",
        "__unique_field__": "id",
        "__spatial_fk__": {"field": "city", "model": "administrative.City", "required": True},
        "wijknaam": "districtName",
        "wijkcode": "id",
    },
    "pdok_neighborhoods": {
        "__geometry__": "geom",
        "__unique__": "buurtcode",
        "__unique_field__": "id",
        "__spatial_fk__": {"field": "district", "model": "administrative.District", "required": False},
        "buurtnaam": "neighborhoodName",
        "buurtcode": "id",
        "aantalInwoners": "currentPopulation",
        "jaar": "populationDate",
    },
    "CBS_Housing": {
        "__unique_fields__": ["city", "year"],
        "__year_source__": "Perioden",
        "__year_field__": "year",
        "__city_source__": "RegioS",
        "__city_field__": "city",
        "SaldoVoorraad_21": "supply_units",
        # demand_units is derived (population / persons per home, HousingSupplyDemand.save()),
        # not the building permits (VergundeNieuwbouw_2) this used to import as demand.
    },
    # Average persons per home = population / households, both whole-gemeente CBS
    # on 1 January; each table fills its own HouseholdSize column and save() derives the ratio.
    "CBS_Households": {
        "__unique_fields__": ["city", "year"],
        "__year_source__": "Perioden",
        "__year_field__": "year",
        "__city_source__": "RegioS",
        "__city_field__": "city",
        "ParticuliereHuishoudens_1": "households",
    },
    "CBS_PopulationJan": {
        "__unique_fields__": ["city", "year"],
        "__year_source__": "Perioden",
        "__year_field__": "year",
        "__city_source__": "RegioS",
        "__city_field__": "city",
        "BevolkingOp1Januari_1": "population",
    },
    # CBS 85173NED "Regionale prognose 2023-2050": one row per gemeente x year x
    # forecast variant, population in thousands.
    "CBS_PopulationForecast": {
        "__unique_fields__": ["city", "year", "scenario"],
        "__year_source__": "Perioden",
        "__year_field__": "year",
        "__city_source__": "RegioIndeling2021",
        "__city_field__": "city",
        "PrognoseInterval": "scenario",
        "TotaleBevolking_1": "population",
        "__value_scales__": {"TotaleBevolking_1": 1000},   # x 1 000 -> people
        "__value_maps__": {"PrognoseInterval": {
            "MW00000": "prognose",   # Prognose (median)
            "MOG0067": "low",        # lower bound of the 67% interval
            "MBG0067": "high",       # upper bound of the 67% interval
        }},
    },

    # -------------------------------- Infrastructure / Built Environment -------------------------------
    
    "pdok_buildings": {
        "__geometry__": "geom",
        "__unique__": "identificatie",
        "__unique_field__": "id",
        "bouwjaar": "constructionYear",
        # "status": "status",
        'gebruiksdoel': "usageFunction",
        'aantal_verblijfsobjecten': "numberUnits",
    },
    "pdok_properties": {
        "__geometry__": "geom",
        "__unique__": "identificatie",
        "__unique_field__": "id",
        "oppervlakte": "grossArea",
        "gebruiksdoel": "usageFunction",
        "openbare_ruimte": "name",
        "huisnummer": "houseNumber",
        "postcode": "postalCode",
    },
        
    
    "pdok_streets": {
        "__geometry__": "geom",
        "__unique__": "gmlId",
        "__unique_field__": "inspireID",
        "text": "name",
    },
    "pdok_landcover_kadaster": {
        "__geometry__": "geom",
        "__spatial_fk__": {"field": "neighborhood", "model": "administrative.Neighborhood", "required": True},
        # Keys here are properties synthesized by _import_atom_gml_features
        # for each plu:ZoningElement, not raw GML element names:
        # hilucslanduseHref is the element's plu:hilucsLandUse xlink:href;
        # title (officialTitle), plan_type (planTypeName codelist value) and
        # valid_from come from the plu:SpatialPlan it belongs to.
        "title": "description",
        "plan_type": "plan_type",
        "valid_from": "valid_from",
        # e.g. .../HILUCSValue/6_3_2_WaterAreasNotInOtherEconomicUse ->
        # physicalEnv.HILUCSLandUse(code="6.3.2"). The table holds the whole
        # INSPIRE codelist; a code missing from it is added with the label
        # spelled out from the URI.
        "__fk_lookup__": [{
            "field": "zone_type",
            "model": "physicalEnv.HILUCSLandUse",
            "source_property": "hilucslanduseHref",
            "lookup_field": "code",
            "parser": "hilucs_href",
            "required": False,
        }],
    },
    "pdok_landcover_brt": {
        "__geometry__": "geom",
        "__spatial_fk__": {"field": "city", "model": "administrative.City", "required": True},
        # landCoverObservationClass is a small bounded codelist (~11 values
        # seen: "urban fabric", "arable land", "pastures", "broad-leaved
        # forest", ...) -- get_or_create a physicalEnv.LandCoverClasses row the
        # first time each value is seen rather than requiring them to be
        # pre-populated, since this is a classification lookup table, not an
        # administrative hierarchy like __spatial_fk__ parents.
        "__fk_lookup__": [{
            "field": "land_cover_type",
            "model": "physicalEnv.LandCoverClasses",
            "source_property": "landCoverObservationClass",
            "lookup_field": "class_name",
            "defaults": {"description": "Auto-created from PDOK BRT Bodemgebruik (pdok_landcover_brt) import."},
        }],
        # observationDate is a full ISO timestamp; LandCoverVector.year is a
        # plain IntegerField.
        "__year_from_date__": "observationDate",
        # LandCoverVector.percentage = this polygon's area as % of its City's
        # area_km2 (resolved by __spatial_fk__ above).
        "__percentage_of_parent__": {"parent_field": "city", "parent_area_attr": "area_km2"},
        "landCoverObservationClass": "land_use",
        # material has no source in this WFS (classification only, no
        # surface/albedo data) -- left unmapped, physicalEnv.LandCoverVector.material
        # is nullable for exactly this reason.
    },

    "bodemdata_soil_map": {
        "__geometry__": "geom",
        "__unique__": "maparea_id",
        "__unique_field__": "mapAreaID",
        # Each polygon points to a SoilType keyed on code + name (soilcode
        # zVp has two names in the 2025 map); SoilType.save() derives the
        # hydrologic soil group and infiltration rate from the name. The main
        # legend unit (first_soilcode/name) colours the map.
        "__fk_lookup__": [{
            "field": "soil_type",
            "model": "physicalEnv.SoilType",
            "lookup": {"code": "soilcode", "name": "normal_soilprofile_name"},
            "defaults_from": {"unitCode": "first_soilcode", "unitName": "first_soilname"},
        }],
    },

    # -------------------------------- Nature & Environment -------------------------------

    "pdok_natura2000": {
        "__geometry__": "geom",
        "__unique__": "gmlID",
        "__unique_field__": "inspireID",
        "__static__": {"protection_type": "N2K"},
        "text": "name",
    },
    "pdok_water_bodies": {
        "__geometry__": "geom",
        "__unique__": "localId",
        "__unique_field__": "localId",
        "geographicalName": "name",
        "type": "water_type",
        "persistence": "persistence",
    },
    "pdok_waterwaysLN": {
        "__geometry__": "geom",
        "__unique__": "localId",
        "__unique_field__": "localId",
        "namespace": "name",
        "persistence": "persistence",
        "lowerWidth": "lowerWidth",
        "upperWidth": "upperWidth",
    },
     "pdok_waterwaysPG": {
        "__geometry__": "geom",
        "__unique__": "localId",
        "__unique_field__": "localId",
        "namespace": "name",
        "persistence": "persistence",
        "lowerWidth": "lowerWidth",
        "upperWidth": "upperWidth",
        },
     
    "bgt_forest": {
        "__geometry__": "geom",
        # fysiek_voorkomen is BGT's physical-terrain classification for
        # begroeidterreindeel (vegetated terrain) -- these three values are
        # the actual forest types; __client_filter__ (read by
        # PDOKImporter.fetch_ogc_features) drops everything else
        # (grasland, struiken, groenvoorziening, ...) before import.
        "__client_filter__": {"property": "fysiek_voorkomen", "in": ["loofbos", "naaldbos", "gemengd bos"]},
        # begroeidterreindeel has no name/title property at all.
        "__name_template__": "{fysiek_voorkomen}",
        "fysiek_voorkomen": "type",
    },
    "bgt_greenspace_park": {
        "__geometry__": "geom",
        "__spatial_fk__": {"field": "city", "model": "administrative.City", "required": True},
        # BGT has no field that means "this is a park" specifically. plus_type
        # values starting with "recreatie" (recreatie, recreatie: sportterrein,
        # recreatie: speeltuin, ...) are the closest available proxy -- broader
        # than parks alone (also covers sports fields/playgrounds).
        "__client_filter__": {"property": "plus_type", "startswith": "recreatie"},
        "__name_template__": "{plus_type}",
        "plus_type": "type",
    },


    # -------------------------------- OpenStreetMap (Overpass) -------------------------------
    # Keys starting with "osm_" are properties synthesized by
    # OSMImporter.to_geojson_features, not raw OSM tags:
    #   osm_id      "osm:<node|way|relation>/<id>", stable across re-imports
    #   osm_name    the name tag, or "<feature_label> <osm_id>" when untagged
    #   osm_class   category from the catalog entry's "osm_classes"
    #   osm_subtype first present tag of the catalog entry's "osm_subtype_tags"
    # Any other key is a raw OSM tag; numeric model fields take the leading
    # number of the tag ("12 m" -> 12.0).

    "osm_parks": {
        "__geometry__": "geom",
        "__unique__": "osm_id",
        "__unique_field__": "sourceID",
        "__spatial_fk__": {"field": "neighborhood", "model": "administrative.Neighborhood", "required": False},
        "osm_name": "name",
        # area comes from Park.save(); OSM has no vegetation type for a park
    },
    "osm_water_bodies": {
        "__geometry__": "geom",
        "__unique__": "osm_id",
        "__unique_field__": "localId",
        "osm_name": "name",
        "osm_subtype": "type",
    },
    "osm_amenities": {
        "__geometry__": "geom",
        "__unique__": "osm_id",
        "__unique_field__": "sourceID",
        "__spatial_fk__": {"field": "neighborhood", "model": "administrative.Neighborhood", "required": False},
        "osm_name": "name",
        "osm_class": "type",
        "osm_subtype": "subtype",
    },
    "osm_trees": {
        "__geometry__": "geom",
        "__unique__": "osm_id",
        "__unique_field__": "sourceID",
        "__spatial_fk__": {"field": "neighborhood", "model": "administrative.Neighborhood", "required": False},
        "species": "species",
        "genus": "genus",
        "leaf_type": "leafType",
        "leaf_cycle": "leafCycle",
        "height": "height_m",
        "circumference": "circumference_m",
        "diameter_crown": "crownDiameter_m",
    },

    "rivm_energy_labels": {
        "__geometry__": "geom",
        "__unique__": "identificatie",
        "__unique_field__": "id",
        "dominant_label": "energyLabel",
        "hoogste_label": "energyLabelHighest",
        "laagste_label": "energyLabelLowest",
        "aant_labels": "energyLabelCount",
    },

    # -------------------------------- Klimaateffectatlas (KEA) WFS -------------------------------
    # docs/KEA_WFS_MAPPING.md. Neighborhood layers write one row per buurt
    # (keyed on neighborhood_id, unknown buurtcodes skipped); building layers
    # are __enrich__ imports onto existing BAG buildings (no new rows, the
    # stored geometry is kept).
    "kea_risicopaalrot_huidig": _kea_neighborhood(
        "buurtcode", {"no_cc_risi": "pileRotRisk_current_pct"},
        __value_scales__={"no_cc_risi": 100}),            # fraction -> %
    "kea_risicopaalrot_2050laag": _kea_neighborhood(
        "buurtcode", {"mild_cc__1": "pileRotRisk_2050low_pct"},
        __value_scales__={"mild_cc__1": 100}),
    "kea_risicopaalrot_2050hoog": _kea_neighborhood(
        "buurtcode", {"sterke_c_2": "pileRotRisk_2050high_pct"},
        __value_scales__={"sterke_c_2": 100}),
    "kea_risicoverschilzetting_2050laag": _kea_neighborhood(
        "buurtcode", {"mild_cc_ri": "settlementRisk_2050low_pct"}),   # already %
    "kea_risicoverschilzetting_2050hoog": _kea_neighborhood(
        "buurtcode", {"sterke_c_1": "settlementRisk_2050high_pct"}),
    "kea_droge_verdiepingen": _kea_neighborhood(
        "BU_CODE", {"VALUE": "dryFloors_pct"}),
    "kea_gevoelstemperatuur_buurt_2012": _kea_neighborhood(
        "bu_code", {"_mean": "petMean_2012_C"}),
    "kea_gevoelstemperatuur_buurt_2022": _kea_neighborhood(
        "buurtcode", {"_mean": "petMean_2022_C", "RIVMClass": "heatClass_2022"}),
    "kea_verkoeling": _kea_neighborhood(
        "bu_code", {"KanGoedVerkoelingVindenBinnen_59": "coolingIndoor_pct",
                    "KanGoedVerkoelingVindenBuiten_60": "coolingOutdoor_pct"}),
    "kea_boomkroon_buurt": _kea_neighborhood(
        "Buurtcode", {"BKBgraad_Tot_percLand_AHN4": "canopyCover_pct",
                      "SHDTot_percLand_AHN4": "shadeTotal_pct",
                      "SHDGroen_percLand_AHN4": "shadeGreen_pct",
                      "SHDGrijs_percLand_AHN4": "shadeGrey_pct"}),
    "kea_huurwoningen": _kea_neighborhood(
        "buurtcode", {"percentage_huurwoningen": "rentalHousing_pct"}, __nodata__=KEA_NODATA),
    "kea_sociaal_economische_status": _kea_neighborhood(
        "buurtcode", {"ses_woa": "socioEconomicStatus"}, __nodata__=KEA_NODATA),
    "kea_broze_gezondheid": _kea_neighborhood(
        "buurtcode", {"broze_gezondheid": "frailHealth_pct"}, __nodata__=KEA_NODATA),
    "kea_sterk_eenzaam": _kea_neighborhood(
        "buurtcode", {"sterk_eenzaam": "severeLoneliness_pct"}, __nodata__=KEA_NODATA),
    "kea_wijktypen": _kea_neighborhood(
        "BU_CODE", {"Wijktype1": "neighborhoodType"}),

    "kea_boomkroon_panden": _kea_building(
        "identificatie", {"perc_bkb": "canopyCover_pct", "bkb_30perc_gehaald": "meetsCanopy30Rule"}),
    # One feature per building block; BAG.Id lists its panden without the
    # leading zero of the 16-digit BAG id.
    "kea_schaduw_op_gebouwen": _kea_building(
        "BAG.Id", {"SOG.Score": "facadeShadeScore"},
        __split__={"property": "BAG.Id", "sep": ",", "zfill": 16}),
    "kea_wateroverlast_panden": _kea_building(
        "identificatie_bag", {"waterdiepte_p99": "floodDepth_p99_m", "waterdiepte_klasse": "floodDepthClass"}),

    "kea_waterschappen": {
        "__geometry__": "geom",
        "__unique__": "WATERSCHAP",
        "__unique_field__": "name",
        "WATERSCHAP": "name",
    },
    "kea_droogtegevoelige_natuur": {
        "__geometry__": "geom",
        "__unique__": "@id",
        "__unique_field__": "sourceID",
        "@id": "sourceID",
        "blad1__naa": "areaName",
        "blad1__gev": "SensibilityLevel",
        # Legend: W = weinig gevoelig, G = gevoelig, Z = zeer gevoelig; no
        # value = not groundwater-dependent (the model default, NotAffected).
        "__value_maps__": {"blad1__gev": {"W": 2, "G": 3, "Z": 4}},   # Low / Medium / High
        # The layer carries no reference year: store the year it was imported.
        "__static__": {"year": date.today().year},
    },
    "kea_klimaatbuffers": {
        "__geometry__": "geom",
        "__unique__": "@id",
        "__unique_field__": "inspireID",
        "@id": "inspireID",
        "Type": "name",
        "__static__": {"protection_type": "OTH"},
    },
}


# ---------------------------------------------------------------------------
# Dataset Catalog
# ---------------------------------------------------------------------------
# Organised by source → category for the UI.
# 'enabled' can be toggled once a handler is implemented.
# Preference: raster (TIFF/COG) > WCS > WFS > WMS

EXTERNAL_DATA_CATALOG = [
    # ══════════════════════════════════════════════════════════════════════════
    # PDOK - Dutch National Geospatial Data Platform
    # ══════════════════════════════════════════════════════════════════════════
    
    # ── Administrative boundaries (WFS - vector) ─────────────────────────────
    {
        "key": "pdok_provinces",
        "source": "pdok",
        "category": "Administrative boundaries",
        "name": "Provinces (Provincies)",
        "description": "All 12 Dutch provinces with official boundaries from the Bestuurlijke Grenzen dataset.",
        "target_model": "administrative.Province",
        "url": "https://service.pdok.nl/kadaster/bestuurlijkegebieden/wfs/v1_0",
        "layer": "bestuurlijkegebieden:Provinciegebied",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_cities",
        "source": "pdok",
        "category": "Administrative boundaries",
        "name": "Municipalities (Gemeenten)",
        "description": "All Dutch municipalities from the Bestuurlijke Grenzen dataset.",
        "target_model": "administrative.City",
        "url": "https://service.pdok.nl/kadaster/bestuurlijkegebieden/wfs/v1_0",
        "layer": "bestuurlijkegebieden:Gemeentegebied",
        "format": "wfs",
        "requires_bbox": True,
        "draw_bbox": True,
        "requires_model": "administrative.Province",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_districts",
        "source": "CBS",
        "category": "Administrative boundaries",
        "name": "Districts - Wijken ",
        "description": "CBS districts polygons from the Wijken en Buurten dataset.",
        "target_model": "administrative.District",
        "url": "https://service.pdok.nl/cbs/wijkenbuurten/2025/wfs/v1_0", # UPDATE YEAR AS NEEDED
        "layer": "wijkenbuurten:wijken",
        "format": "wfs",
        "requires_bbox": True,
        "bbox_from": "administrative.City",  # area of interest is picked from imported cities
        "requires_model": "administrative.City",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_neighborhoods",
        "source": "CBS",
        "category": "Administrative boundaries",
        "name": "Neighborhoods - Buurten",
        "description": "CBS neighborhood polygons from the Wijken en Buurten dataset.",
        "target_model": "administrative.Neighborhood",
        "url": "https://service.pdok.nl/cbs/wijkenbuurten/2025/wfs/v1_0", # UPDATE YEAR AS NEEDED
        "layer": "wijkenbuurten:buurten",
        "format": "wfs",
        "requires_bbox": True,
        "bbox_from": "administrative.District",  # area of interest is picked from imported districts
        "requires_model": "administrative.District",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    
    {
      "key": "CBS_Housing",
      "source": "CBS",
      "category": "Housing",
      "name": "Housing Lifecycle (86098NED)",
      "description": "CBS housing stock lifecycle per municipality: inventory, new construction, permits, demolitions.",
      "target_model": "housing.HousingSupplyDemand",
      "table_id": "86098NED",
      "format": "odata",
      "requires_bbox": True,
      "params": {
          "filter": "Gebruiksfunctie eq 'A045364' and startswith(RegioS,'GM') and substringof('KW04',Perioden)",
          "select": ["RegioS", "Perioden", "SaldoVoorraad_21"],
      },
      "enabled": True,
    },

    {
      "key": "CBS_Households",
      "source": "CBS",
      "category": "Housing",
      "name": "Private households 2014- (86291NED)",
      "description": "CBS number of private households per municipality on 1 January. With the population on 1 January (CBS_PopulationJan) it gives the average number of persons per home, the housing dashboard's slider.",
      "target_model": "housing.HouseholdSize",
      "table_id": "86291NED",
      "format": "odata",
      "requires_bbox": True,
      "params": {
          "filter": "LeeftijdReferentiepersoon eq '10000' and Huishoudenssamenstelling eq 'T001139' and GrootteVanHetHuishouden eq 'T001106' and startswith(RegioS,'GM') and substringof('JJ00',Perioden)",
          "select": ["RegioS", "Perioden", "ParticuliereHuishoudens_1"],
      },
      "enabled": True,
    },

    {
      "key": "CBS_PopulationJan",
      "source": "CBS",
      "category": "Housing",
      "name": "Population on 1 January (03759NED)",
      "description": "CBS total population per municipality on 1 January. Whole-gemeente figure, so the average persons per home is right even when only some neighborhoods are imported.",
      "target_model": "housing.HouseholdSize",
      "table_id": "03759ned",
      "format": "odata",
      "requires_bbox": True,
      "params": {
          "filter": "Geslacht eq 'T001038' and Leeftijd eq '10000' and BurgerlijkeStaat eq 'T001019' and startswith(RegioS,'GM') and substringof('JJ00',Perioden)",
          "select": ["RegioS", "Perioden", "BevolkingOp1Januari_1"],
      },
      "enabled": True,
    },

    {
      "key": "CBS_PopulationForecast",
      "source": "CBS",
      "category": "Demographics",
      "name": "Population forecast 2023-2050 (85173NED)",
      "description": "CBS regional population forecast per municipality: median and the lower/upper bound of the 67% interval, 2023-2050. Feeds the population curve of the dashboard.",
      "target_model": "administrative.PopulationProjection",
      "table_id": "85173NED",
      "format": "odata",
      "requires_bbox": True,
      "params": {
          "filter": "Leeftijd eq '10000' and startswith(RegioIndeling2021,'GM')",
          "select": ["RegioIndeling2021", "PrognoseInterval", "Perioden", "TotaleBevolking_1"],
          "region_field": "RegioIndeling2021",
      },
      "enabled": True,
    },

    # ── Built environment (WFS - vector) ─────────────────────────────────────
    {
        "key": "pdok_buildings",
        "source": "pdok",
        "category": "Built environment",
        "name": "Buildings (BAG Panden)",
        "description": "All buildings from the Basisregistratie Adressen en Gebouwen (BAG).",
        "target_model": "builtup.Building",
        "url": "https://service.pdok.nl/lv/bag/wfs/v2_0",
        "layer": "bag:pand",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "slow": True,
        "slow_reason": "BAG Panden is a very large dataset; even with a bounding box, it may take several minutes to load.",
        "enabled": True,
    },
    {
        "key": "pdok_properties",
        "source": "pdok",
        "category": "Built environment",
        "name": "Properties (BAG Verblijfsobjecten)",
        "description": "All properties from the Basisregistratie Adressen en Gebouwen (BAG).",
        "target_model": "builtup.Property",
        "url": "https://service.pdok.nl/lv/bag/wfs/v2_0",
        "layer": "bag:verblijfsobject",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "slow": True,
        "slow_reason": "BAG Verblijfsobjecten is a very large dataset; even with a bounding box, it may take several minutes to load.",
        "enabled": True,
    },
    
    {
        "key": "pdok_streets",
        "source": "pdok",
        "category": "Built environment",
        "name": "Road Network (Vervoersnetwerken)",
        "description": "General Road network from Inspire.",
        "target_model": "builtup.Street",
        "url": "https://service.pdok.nl/rws/vervoersnetwerken-wegen-netwerk/wfs/v1_0",
        "layer": "vervoersnetwerken:road_link",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },

    # ── Nature & Environment (WFS - vector) ──────────────────────────────────
    {
        "key": "pdok_natura2000",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Natura 2000 Areas",
        "description": "European protected nature areas in the Netherlands.",
        "target_model": "nature.ProtectedArea",
        "url": "https://service.pdok.nl/rvo/natura2000/wfs/v1_0",
        "layer": "natura2000",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_water_bodies",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Water Bodies (Kadaster BRT Hydrografie)",
        "description": "Lakes, ponds, and other water bodies from Kadaster.",
        "target_model": "nature.WaterBodies",
        "url": "https://service.pdok.nl/kadaster/brt-hydrografie/wfs/v1_0",
        "layer": "brt-hydrografie:standingwater",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "pdok_waterwaysLN",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Watercourse Lines",
        "description": "Waterways and rivers from the Kadaster dataset.",
        "target_model": "nature.WaterBodies",
        "url": "https://service.pdok.nl/kadaster/brt-hydrografie/wfs/v1_0",
        "layer": "brt-hydrografie:watercourse_linestring",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    
    {
        "key": "pdok_waterwaysPG",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Watercourse Polygons",
        "description": "Waterways and rivers from the Kadaster dataset.",
        "target_model": "nature.WaterBodies",
        "url": "https://service.pdok.nl/kadaster/brt-hydrografie/wfs/v1_0",
        "layer": "brt-hydrografie:watercourse_linestring",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },

    {
        "key": "bgt_forest",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Forest (BGT begroeidterreindeel)",
        "description": "Forest patches (loofbos/naaldbos/gemengd bos) from Kadaster's BGT, per-parcel resolution.",
        "target_model": "nature.Forests",
        "url": "https://api.pdok.nl/lv/bgt/ogc/v1",
        "collection": "begroeidterreindeel",
        "format": "ogc_api",
        "params": {"srsName": "EPSG:28992"},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "bgt_greenspace_park",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Green Space / Parks (BGT functioneelgebied)",
        "description": "Recreation-designated green space (parks, sports fields, playgrounds) from Kadaster's BGT.",
        "target_model": "nature.GreenSpaces",
        "url": "https://api.pdok.nl/lv/bgt/ogc/v1",
        "collection": "functioneelgebied",
        "format": "ogc_api",
        "params": {"srsName": "EPSG:28992"},
        "requires_bbox": True,
        "enabled": True,
    },

    # ── Energy ───────────────────────────────────────────────────────────────
    {
        "key": "rivm_energy_labels",
        "source": "rivm",
        "category": "Energy",
        "name": "Building Energy Labels (RVO EP-Online, via RIVM)",
        # PDOK never carried this dataset (the old service.pdok.nl/rvo/epontline
        # URL 404s and has no replacement there). RVO's own EP-Online API is
        # per-address and requires an API key. RIVM republishes the same
        # register, pre-aggregated to one polygon per BAG pand, as an open WFS
        # (this is what backs the "Energielabels van gebouwen" layer on
        # atlasleefomgeving.nl). Writes onto builtup.Building by id==identificatie,
        # so run "Buildings (BAG Panden)" first for rows to attach labels to.
        "description": "Per-building aggregate of registered EP-Online energy labels (dominant/highest/lowest label, label count), sourced from RVO and republished by RIVM. Updated monthly. Requires bounding box; import BAG Panden first so buildings exist to attach labels to.",
        "target_model": "builtup.Building",
        "url": "https://data.rivm.nl/geo/nl/wfs",
        "layer": "rvo_energielabels",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },

    # ── Elevation/Terrain (Raster) ───────────────────────────────────────────
    {
        "key": "pdok_dem_ahn_raster",
        "source": "pdok",
        "category": "Elevation & Terrain",
        "name": "Digital Elevation Model (AHN4 DTM)",
        "description": "High-resolution terrain model from AHN4 via WCS.",
        "target_model": "physicalEnv.DigitalElevationModel",
        "url": "https://service.pdok.nl/rws/actueel-hoogtebestand-nederland/wcs/v1_0",
        "wcs_url": "https://service.pdok.nl/rws/actueel-hoogtebestand-nederland/wcs/v1_0",
        "layer": "dtm_05m",
        "format": "wcs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "resolution_m": 0.5,
        "slow": True,
        "slow_reason": "0.5m resolution means large areas are split into many tiled WCS requests and mosaicked — a whole city can take several minutes.",
        "enabled": True,
    },
    {
        "key": "pdok_dem_ahn_wms",
        "source": "pdok",
        "category": "Elevation & Terrain",
        "name": "Digital Elevation Model (AHN4 WMS)",
        "description": "WMS visualization layer for AHN4 elevation data.",
        "target_model": "physicalEnv.DigitalElevationModelWMS",
        "url": "https://service.pdok.nl/rws/ahn/wms/v1_0",
        "layer": "dtm_05m",
        "format": "wms",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_dsm_ahn_raster",
        "source": "pdok",
        "category": "Elevation & Terrain",
        "name": "Digital Surface Model (AHN4 DSM)",
        "description": "High-resolution surface model (including buildings/trees) from AHN4 via WCS.",
        "target_model": "physicalEnv.DigitalSurfaceModel",
        "url": "https://service.pdok.nl/rws/actueel-hoogtebestand-nederland/wcs/v1_0",
        "wcs_url": "https://service.pdok.nl/rws/actueel-hoogtebestand-nederland/wcs/v1_0",
        "layer": "dsm_05m",
        "format": "wcs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "resolution_m": 0.5,
        "slow": True,
        "slow_reason": "0.5m resolution means large areas are split into many tiled WCS requests and mosaicked — a whole city can take several minutes.",
        "enabled": True,
    },
    {
        "key": "pdok_dsm_ahn_wms",
        "source": "pdok",
        "category": "Elevation & Terrain",
        "name": "Digital Surface Model (AHN4 DSM WMS)",
        "description": "WMS visualization layer for AHN4 surface model.",
        "target_model": "physicalEnv.DigitalSurfaceModelWMS",
        "url": "https://service.pdok.nl/rws/ahn/wms/v1_0",
        "layer": "dsm_05m",
        "format": "wms",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },

    # ── Land Cover (Raster) ──────────────────────────────────────────────────
    {
        "key": "pdok_landcover_lgn",
        "source": "pdok",
        "category": "Imagery / Spectral Indices",
        "name": "Land Cover (LGN2025) WMS",
        "description": "Dutch national land use map at 5m resolution via WMS.",
        "target_model": "physicalEnv.LandCoverWMS",
        "url": "https://service.pdok.nl/wur/landelijk-grondgebruik-nederland/wms/v1_0",
        "layer": "lgn-actueel",
        "format": "wms",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "resolution_m": 5.0,
        "enabled": True,
    },

    # ── Land Cover (Vector) ──────────────────────────────────────────────────
    {
        "key": "pdok_landcover_brt",
        "source": "pdok",
        "category": "Imagery / Spectral Indices",
        "name": "Bodemgebruik - Land Cover (INSPIRE harmonised) WFS",
        "description": "Classified Dutch land cover polygons (BRT/Top10NL-derived) from Kadaster, INSPIRE harmonised.",
        "target_model": "physicalEnv.LandCoverVector",
        "url": "https://service.pdok.nl/kadaster/brt-bodemgebruik/wfs/v1_0",
        "layer": "lc:landcoverunit",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },

    # ── Soil (WFS - vector) ──────────────────────────────────────────────────
    {
        "key": "bodemdata_soil_map",
        "source": "bodemdata",
        "category": "Elevation & Terrain",
        "name": "Soil Map 1:50 000 (Bodemkaart, BIS Nederland)",
        "description": "Soil polygons of the Dutch soil map (2025 edition) with soil code and name; each soil type gets an SCS hydrologic soil group (A-D) and infiltration rate. Feeds the infiltration indicator of the water dashboard together with land cover.",
        "target_model": "physicalEnv.SoilArea",
        "url": "https://maps.bodemdata.nl/geoserver/bodem/ows",
        "layer": "bodem:Bodemkaart50000_v2025",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },
    # Groundwater depth maps of the same GeoServer (WCS only; its WFS has
    # just the point observations behind them). 50 m, EPSG:28992, uint8 in
    # cm below ground level, capped at 254 (= 254 cm or deeper), 255 nodata.
    {
        "key": "bodemdata_ghg",
        "source": "bodemdata",
        "category": "Elevation & Terrain",
        "name": "Groundwater Depth, wet season (GHG, BIS Nederland)",
        "description": "Mean highest groundwater level (GHG) in cm below ground, 50 m grid. Where it is under 60 cm the infiltration indicator treats the soil as SCS group D.",
        "target_model": "physicalEnv.GroundwaterDepth",
        "url": "https://maps.bodemdata.nl/geoserver/ows",
        "layer": "bodem__ghg-mediaan",
        "format": "wcs",
        "statistic": "GHG",
        "wcs_axis_labels": ["X", "Y"],
        "params": {"srsName": "EPSG:28992"},
        "requires_bbox": True,
        "resolution_m": 50.0,
        "enabled": True,
    },
    {
        "key": "bodemdata_glg",
        "source": "bodemdata",
        "category": "Elevation & Terrain",
        "name": "Groundwater Depth, dry season (GLG, BIS Nederland)",
        "description": "Mean lowest groundwater level (GLG) in cm below ground, 50 m grid.",
        "target_model": "physicalEnv.GroundwaterDepth",
        "url": "https://maps.bodemdata.nl/geoserver/ows",
        "layer": "bodem__glg-mediaan",
        "format": "wcs",
        "statistic": "GLG",
        "wcs_axis_labels": ["X", "Y"],
        "params": {"srsName": "EPSG:28992"},
        "requires_bbox": True,
        "resolution_m": 50.0,
        "enabled": True,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Sentinel-2 - Copernicus Earth Observation
    # ══════════════════════════════════════════════════════════════════════════
    
    # ── Land Cover (Raster) ──────────────────────────────────────────────────
    {
        "key": "pdok_landcover_kadaster",
        "source": "pdok",
        "category": "Built environment",
        "name": "Planned Land Use / Zoning Plans (INSPIRE harmonised) ATOM Feed",
        # This is an INSPIRE Planned Land Use feed of Dutch zoning plans
        # (bestemmingsplannen) from Kadaster's ruimtelijkeplannen.nl. Its
        # plu:ZoningElement features (one zoning function each, classified by
        # HILUCS) become builtup.ZoningArea rows; it has no land-cover or
        # surface-material attribute, so it isn't physicalEnv.LandCoverVector.
        "description": "Zoning elements of Dutch zoning plans (bestemmingsplannen) from Kadaster's Ruimtelijkeplannen register, classified by INSPIRE HILUCS land use.",
        "target_model": "builtup.ZoningArea",
        "url": "https://service.pdok.nl/kadaster/ruimtelijke-plannen-gepland-landgebruik/atom/index.xml",
        "format": "atom",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "sentinel2_worldcover_wms",
        "source": "sentinel2",
        "category": "Imagery / Spectral Indices",
        "name": "ESA WorldCover 10m (WMS)",
        "description": "WMS visualization of global land cover.",
        "target_model": "physicalEnv.LandCoverWMS",
        "url": "https://services.terrascope.be/wms/v2",
        "layer": "WORLDCOVER_2021_MAP",
        "format": "wms",
        "params": {"srsName": "EPSG:4326"},
        "enabled": True,
    },

    # ── Spectral Indices (openEO) ─────────────────────────────────────────────
    # Formerly served via the Sentinel Hub Process API, which is now a paid
    # tier. Re-implemented as openEO band math against the Copernicus Data
    # Space Ecosystem's free openEO backend — see
    # https://documentation.dataspace.copernicus.eu/APIs/openEO/Python_Client/Python.html
    # Auth is a CDSE OIDC client_id/client_secret (client-credentials grant),
    # not a single bearer token.
    {
        "key": "sentinel2_ndvi_raster",
        "source": "sentinel2",
        "category": "Imagery / Spectral Indices",
        "name": "NDVI (Vegetation Index)",
        "description": "Normalized Difference Vegetation Index computed from Sentinel-2 bands via openEO.",
        "target_model": "physicalEnv.LandCoverRaster",
        "url": "https://openeo.dataspace.copernicus.eu",
        "format": "openeo",
        "openeo_process": "NDVI",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
        "slow": True,
        "slow_reason": "Runs as a single long-lived server-side computation on Copernicus Data Space's openEO backend — typically takes a few minutes.",
        "enabled": True,
    },
    {
        "key": "sentinel2_true_color_raster",
        "source": "sentinel2",
        "category": "Imagery / Spectral Indices",
        "name": "True Color (RGB)",
        "description": "Natural color composite from Sentinel-2 visible bands via openEO.",
        "target_model": "physicalEnv.SatelliteImagery",
        "url": "https://openeo.dataspace.copernicus.eu",
        "format": "openeo",
        "openeo_process": "TRUE_COLOR",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
        "slow": True,
        "slow_reason": "Runs as a single long-lived server-side computation on Copernicus Data Space's openEO backend — typically takes a few minutes.",
        "enabled": True,
    },
    {
        "key": "sentinel2_ndwi_raster",
        "source": "sentinel2",
        "category": "Imagery / Spectral Indices",
        "name": "NDWI (Water Index)",
        "description": "Normalized Difference Water Index for water body detection via openEO.",
        "target_model": "physicalEnv.LandCoverRaster",
        "url": "https://openeo.dataspace.copernicus.eu",
        "format": "openeo",
        "openeo_process": "NDWI",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
        "slow": True,
        "slow_reason": "Runs as a single long-lived server-side computation on Copernicus Data Space's openEO backend — typically takes a few minutes.",
        "enabled": True,
    },
    {
        "key": "sentinel2_moisture_raster",
        "source": "sentinel2",
        "category": "Imagery / Spectral Indices",
        "name": "Moisture Index",
        "description": "Normalized Difference Moisture Index for vegetation water content via openEO.",
        "target_model": "physicalEnv.LandCoverRaster",
        "url": "https://openeo.dataspace.copernicus.eu",
        "format": "openeo",
        "openeo_process": "MOISTURE_INDEX",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
        "slow": True,
        "slow_reason": "Runs as a single long-lived server-side computation on Copernicus Data Space's openEO backend — typically takes a few minutes.",
        "enabled": True,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Google Earth Engine
    # ══════════════════════════════════════════════════════════════════════════
    
    # ── Water ────────────────────────────────────────────────────────────────
    {
        "key": "gee_global_surface_water",
        "source": "gee",
        "category": "Nature & Environment",
        "name": "Global Surface Water Occurrence",
        "description": "JRC Global Surface Water dataset showing water occurrence frequency (1984-2021).",
        "target_model": "nature.WaterBodies",
        "asset_id": "JRC/GSW1_4/GlobalSurfaceWater",
        "band": "occurrence",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_water_seasonality",
        "source": "gee",
        "category": "Nature & Environment",
        "name": "Water Seasonality",
        "description": "Number of months per year with water presence.",
        "target_model": "physicalEnv.LandCoverRaster",
        "asset_id": "JRC/GSW1_4/GlobalSurfaceWater",
        "band": "seasonality",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "resolution_m": 30.0,
        "satellite_type": "Landsat",
        "enabled": True,
    },

    # ── Forests ──────────────────────────────────────────────────────────────
    {
        "key": "gee_forest_cover",
        "source": "gee",
        "category": "Nature & Environment",
        "name": "Global Forest Cover (2000)",
        "description": "Hansen Global Forest Change - tree cover percentage in year 2000.",
        "target_model": "nature.Forests",
        "asset_id": "UMD/hansen/global_forest_change_2023_v1_11",
        "band": "treecover2000",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_forest_loss",
        "source": "gee",
        "category": "Nature & Environment",
        "name": "Forest Loss Year",
        "description": "Year of forest loss event (2001-2023).",
        "target_model": "physicalEnv.LandCoverRaster",
        "asset_id": "UMD/hansen/global_forest_change_2023_v1_11",
        "band": "lossyear",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "resolution_m": 30.0,
        "satellite_type": "Landsat",
        "enabled": True,
    },
    {
        "key": "gee_forest_gain",
        "source": "gee",
        "category": "Nature & Environment",
        "name": "Forest Gain (2000-2012)",
        "description": "Areas of forest gain between 2000-2012.",
        "target_model": "physicalEnv.LandCoverRaster",
        "asset_id": "UMD/hansen/global_forest_change_2023_v1_11",
        "band": "gain",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "resolution_m": 30.0,
        "satellite_type": "Landsat",
        "enabled": True,
    },

    # ── Climate/Weather ──────────────────────────────────────────────────────
    {
        "key": "gee_precipitation",
        "source": "gee",
        "category": "Climate",
        "name": "Precipitation (CHIRPS)",
        "description": "CHIRPS daily precipitation data. Requires date range.",
        "target_model": "weather.PrecipitationRaster",
        "asset_id": "UCSB-CHG/CHIRPS/DAILY",
        "band": "precipitation",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "slow": True,
        "slow_reason": "Server-side compositing across an image collection on Google Earth Engine can take a while, especially over a wide date range.",
        "enabled": True,
    },
    {
        "key": "gee_temperature",
        "source": "gee",
        "category": "Climate",
        "name": "Land Surface Temperature (MODIS)",
        "description": "MODIS 8-day land surface temperature. Requires date range.",
        "target_model": "weather.TemperatureRaster",
        "asset_id": "MODIS/061/MOD11A2",
        "band": "LST_Day_1km",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "slow": True,
        "slow_reason": "Server-side compositing across an image collection on Google Earth Engine can take a while, especially over a wide date range.",
        "enabled": True,
    },
    {
        "key": "gee_wind_speed",
        "source": "gee",
        "category": "Climate",
        "name": "Wind Speed (ERA5)",
        "description": "ERA5 reanalysis wind speed data. Requires date range.",
        "target_model": "weather.WindSpeedRaster",
        "asset_id": "ECMWF/ERA5_LAND/HOURLY",
        "band": "u_component_of_wind_10m",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "slow": True,
        "slow_reason": "Server-side compositing across an image collection on Google Earth Engine can take a while, especially over a wide date range.",
        "enabled": True,
    },

    # ── Land Cover ───────────────────────────────────────────────────────────
    {
        "key": "gee_dynamic_world",
        "source": "gee",
        "category": "Imagery / Spectral Indices",
        "name": "Dynamic World (Near Real-Time)",
        "description": "Google/WRI 10m land cover classification. Requires date range.",
        "target_model": "physicalEnv.LandCoverRaster",
        "asset_id": "GOOGLE/DYNAMICWORLD/V1",
        "band": "label",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
        "slow": True,
        "slow_reason": "Server-side compositing across an image collection on Google Earth Engine can take a while, especially over a wide date range.",
        "enabled": True,
    },
    {
        "key": "gee_soil_moisture",
        "source": "gee",
        "category": "Imagery / Spectral Indices",
        "name": "Soil Moisture (SMAP)",
        "description": "NASA SMAP soil moisture data. Requires date range.",
        "target_model": "physicalEnv.LandCoverRaster",
        "asset_id": "NASA/SMAP/SPL4SMGP/007",
        "band": "sm_surface",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 9000.0,
        "satellite_type": "SMAP",
        "slow": True,
        "slow_reason": "Server-side compositing across an image collection on Google Earth Engine can take a while, especially over a wide date range.",
        "enabled": True,
    },

    # ── Demographics ─────────────────────────────────────────────────────────
    {
        "key": "gee_population_density",
        "source": "gee",
        "category": "Demographics",
        "name": "Population Density (HRSL)",
        "description": "High Resolution Settlement Layer (HRSL) population density estimates, derived from computer vision analysis of building locations (Meta Connectivity Lab / CIESIN).",
        "target_model": "physicalEnv.SatelliteImagery",
        "asset_id": "projects/sat-io/open-datasets/hrsl/hrslpop",
        "band": "b1",
        "index_override": "HRSL_POP",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "resolution_m": 30.0,
        "satellite_type": "DigitalGlobe (HRSL)",
        "enabled": True,
    },
    {
        "key": "gee_nighttime_lights",
        "source": "gee",
        "category": "Demographics",
        "name": "Nighttime Lights (VIIRS)",
        "description": "VIIRS nighttime lights as proxy for urban development.",
        "target_model": "physicalEnv.SatelliteImagery",
        "asset_id": "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG",
        "band": "avg_rad",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 500.0,
        "satellite_type": "VIIRS",
        "slow": True,
        "slow_reason": "Server-side compositing across an image collection on Google Earth Engine can take a while, especially over a wide date range.",
        "enabled": True,
    },

    # ── KNMI Data Platform ───────────────────────────────────────────────────
    {
        "key": "knmi_wbgt",
        "source": "knmi",
        "category": "Climate",
        "name": "Wet Bulb Globe Temperature (KNMI, latest)",
        "description": "Latest heat-stress measure (WBGT) published by KNMI: air temperature, humidity, wind and radiation combined. Always fetches the newest file; needs KNMI_API_KEY on the server.",
        "target_model": "urban_heat.WetBulbGlobeTemperature",
        "api_base": "https://api.dataplatform.knmi.nl/open-data/v1",
        "dataset_name": "wet_bulb_globe_temperature",
        "dataset_version": "3.0",
        "measurement_method": "KNMI WBGT analysis",
        "format": "raster",
        # The key lives in the server's .env (KNMI_API_KEY), so the user
        # supplies nothing and no bbox is needed: the whole grid is stored.
        "enabled": True,
    },
    {
        "key": "knmi_radar_forecast",
        "source": "knmi",
        "category": "Climate",
        "name": "KNMI Radar Forecast",
        "description": "Precipitation radar with a two-hour nowcast from KNMI, animated on the map and refreshed every 5 minutes. Registers a WMS layer only; tiles are fetched live through the server, which sends KNMI_API_KEY.",
        "target_model": "weather.WMSLayer",
        "url": "https://api.dataplatform.knmi.nl/wms/adaguc-server?DATASET=radar_forecast_2.0",
        "layer": "precipitation_nowcast",
        "format": "wms",
        # The row's name is the tile proxy's URL segment (/wms/<name>/);
        # keep it equal to rows created earlier through the admin.
        "wms_name": "radar_forecast_2.0",
        # KNMI answers GetCapabilities/GetLegendGraphic only with the API
        # key, which the browser never sees, so no legend is looked up.
        "legend_url": "",
        "wms_options": {
            "has_time_dimension": True,
            "time_frame_count": 12,
            "time_refresh_minutes": 5,
            "api_key_setting": "KNMI_API_KEY",
        },
        "enabled": True,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # OpenStreetMap - via the Overpass API
    # ══════════════════════════════════════════════════════════════════════════
    # "osm_query" holds Overpass QL statements without bbox or output: the
    # importer adds a global [bbox:...] and picks `out center` for point
    # models and `out geom` for the rest. "feature_label" names untagged
    # features. The public Overpass instance is shared and rate limited, so
    # keep areas city-sized; OVERPASS_URL in .env points at another instance.
    {
        "key": "osm_parks",
        "source": "osm",
        "category": "Nature & Environment",
        "name": "Parks (OpenStreetMap)",
        "description": "Park polygons tagged leisure=park in OpenStreetMap. Feeds the park area per inhabitant of the built-up dashboard; import neighborhoods first so parks are attributed to them.",
        "target_model": "builtup.Park",
        "url": "https://overpass-api.de/api/interpreter",
        "format": "overpass",
        "osm_query": ['way["leisure"="park"]', 'relation["leisure"="park"]'],
        "feature_label": "Park",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "osm_water_bodies",
        "source": "osm",
        "category": "Nature & Environment",
        "name": "Water Bodies (OpenStreetMap)",
        "description": "Lakes, ponds, canals, reservoirs and basins mapped as water areas (natural=water, landuse=reservoir/basin) in OpenStreetMap.",
        "target_model": "nature.WaterBodies",
        "url": "https://overpass-api.de/api/interpreter",
        "format": "overpass",
        "osm_query": [
            'way["natural"="water"]', 'relation["natural"="water"]',
            'way["landuse"~"^(reservoir|basin)$"]', 'relation["landuse"~"^(reservoir|basin)$"]',
        ],
        # water=lake/pond/canal/... is the finer type; fall back to the landuse
        # or natural value when it is missing
        "osm_subtype_tags": ["water", "landuse", "natural"],
        "feature_label": "Water body",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "osm_amenities",
        "source": "osm",
        "category": "Built environment",
        "name": "Amenities (OpenStreetMap)",
        "description": "Schools, hospitals and clinics, fire and police stations, marketplaces and transport stations mapped as points (OSM nodes) in OpenStreetMap. Feeds the facilities per inhabitant of the built-up dashboard.",
        "target_model": "builtup.Facility",
        "url": "https://overpass-api.de/api/interpreter",
        "format": "overpass",
        # Nodes only: an amenity drawn as a way or relation (e.g. a school's
        # grounds) is not imported, even when the same facility has no node.
        "osm_query": [
            'node["amenity"~"^(school|kindergarten|college|university|hospital|clinic|fire_station|police|marketplace|bus_station|ferry_terminal)$"]',
            'node["railway"="station"]',
        ],
        # tag -> {OSM value: Facility.type}; the first matching tag wins
        "osm_classes": {
            "amenity": {
                "school": "school", "kindergarten": "school", "college": "school", "university": "school",
                "hospital": "hospital", "clinic": "hospital",
                "fire_station": "fire_station",
                "police": "police_station",
                "marketplace": "market",
                "bus_station": "transportNode", "ferry_terminal": "transportNode",
            },
            "railway": {"station": "transportNode"},
        },
        "osm_subtype_tags": ["amenity", "railway"],
        "feature_label": "Facility",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "osm_trees",
        "source": "osm",
        "category": "Nature & Environment",
        "name": "Trees (OpenStreetMap)",
        "description": "Individual trees (natural=tree) with species, genus, leaf type, height and crown diameter where mapped. Coverage varies a lot between cities.",
        "target_model": "nature.Tree",
        "url": "https://overpass-api.de/api/interpreter",
        "format": "overpass",
        "osm_query": ['node["natural"="tree"]'],
        "feature_label": "Tree",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "slow": True,
        "slow_reason": "Well-mapped cities have tens of thousands of trees; a whole city can take a minute or two on the public Overpass server.",
        "enabled": True,
    },
]

# ══════════════════════════════════════════════════════════════════════════
# Klimaateffectatlas (KEA) - public WFS of the climate-effect atlas
# ══════════════════════════════════════════════════════════════════════════
# docs/KEA_WFS_MAPPING.md lists every KEA WFS layer, what is imported and
# why the rest is not. Layer names with a date stamp (_v20260722,
# _20251120) are the publisher's versions: update them when KEA republishes.
_NEIGHBORHOODS_FIRST = "Import neighborhoods first; buurten that are not stored are skipped."
_BUILDINGS_FIRST = "Writes onto existing BAG buildings only (import Buildings (BAG Panden) first); no buildings are created and their geometry is kept."


def _kea_entry(key, layer, name, description, category, target_model, requires_model):
    return {
        "key": key,
        "source": "kea",
        "category": category,
        "name": name,
        "description": description,
        "target_model": target_model,
        "url": KEA_WFS_URL,
        "layer": f"kea_public:{layer}",
        "format": "wfs",
        "params": {"srsName": f"EPSG:{coordinate_system}"},
        "requires_bbox": True,
        "requires_model": requires_model,
        "enabled": True,
    }


_N, _B = "administrative.Neighborhood", "builtup.Building"
EXTERNAL_DATA_CATALOG += [
    # ── Built environment: foundations and flooding ──────────────────────────
    _kea_entry("kea_risicopaalrot_huidig", "risicopaalrot_huidig", "Pile Rot Risk, current (KEA)",
               f"Share of buildings per neighborhood at risk of wooden pile rot in the current climate. {_NEIGHBORHOODS_FIRST}",
               "Built environment", "builtup.NeighborhoodClimateRisk", _N),
    _kea_entry("kea_risicopaalrot_2050laag", "risicopaalrot_2050laag", "Pile Rot Risk, 2050 low (KEA)",
               f"Share of buildings at risk of pile rot in 2050, low climate scenario. {_NEIGHBORHOODS_FIRST}",
               "Built environment", "builtup.NeighborhoodClimateRisk", _N),
    _kea_entry("kea_risicopaalrot_2050hoog", "risicopaalrot_2050hoog", "Pile Rot Risk, 2050 high (KEA)",
               f"Share of buildings at risk of pile rot in 2050, high climate scenario. {_NEIGHBORHOODS_FIRST}",
               "Built environment", "builtup.NeighborhoodClimateRisk", _N),
    _kea_entry("kea_risicoverschilzetting_2050laag", "risicoverschilzetting_2050laag", "Differential Settlement Risk, 2050 low (KEA)",
               f"Share of buildings at risk of differential settlement in 2050, low scenario. {_NEIGHBORHOODS_FIRST}",
               "Built environment", "builtup.NeighborhoodClimateRisk", _N),
    _kea_entry("kea_risicoverschilzetting_2050hoog", "risicoverschilzetting_2050hoog", "Differential Settlement Risk, 2050 high (KEA)",
               f"Share of buildings at risk of differential settlement in 2050, high scenario. {_NEIGHBORHOODS_FIRST}",
               "Built environment", "builtup.NeighborhoodClimateRisk", _N),
    _kea_entry("kea_droge_verdiepingen", "droge_verdiepingen_extreem_kleine_kans_20251120", "Dry Floors in an Extreme Flood (KEA)",
               f"Share of floors per neighborhood that stay dry in an extremely unlikely flood. {_NEIGHBORHOODS_FIRST}",
               "Built environment", "builtup.NeighborhoodClimateRisk", _N),
    _kea_entry("kea_wateroverlast_panden", "nl_fcab_omgevingsscore_wateroverlast_v20260806", "Cloudburst Water Depth per Building (KEA)",
               f"99th percentile water depth around each building in a 70 mm/h cloudburst, with its depth class. {_BUILDINGS_FIRST}",
               "Built environment", _B, _B),
    _kea_entry("kea_boomkroon_panden", "RMK_30percBKB_AHN4", "Tree Canopy around Buildings, 3-30-300 (KEA)",
               f"Canopy cover around each building (AHN4) and whether the 30% canopy rule is met. {_BUILDINGS_FIRST}",
               "Built environment", _B, _B),
    _kea_entry("kea_schaduw_op_gebouwen", "Schaduw op gebouwen", "Facade Shade Score (KEA)",
               f"Shade on the facades per building block, copied to every building of the block. {_BUILDINGS_FIRST}",
               "Built environment", _B, _B),
    # ── Climate: heat and shade ──────────────────────────────────────────────
    _kea_entry("kea_gevoelstemperatuur_buurt_2012", "GevoelstemperatuurBuurt_2012", "Perceived Temperature per Neighborhood, 2012 (KEA)",
               f"Mean PET on a hot summer day per neighborhood, 2012 surface model. Buurt codes of 2012 that no longer exist are skipped. {_NEIGHBORHOODS_FIRST}",
               "Climate", "urban_heat.NeighborhoodHeat", _N),
    _kea_entry("kea_gevoelstemperatuur_buurt_2022", "GevoelstemperatuurBuurt_2022", "Perceived Temperature per Neighborhood, 2022 (KEA)",
               f"Mean PET on a hot summer day per neighborhood and its RIVM class, 2022 surface model. {_NEIGHBORHOODS_FIRST}",
               "Climate", "urban_heat.NeighborhoodHeat", _N),
    _kea_entry("kea_verkoeling", "SchaduwOpGebouwen_VerkoelingBinnen", "Cooling Indoors and Outdoors (KEA)",
               f"Share of residents who can find cooling indoors and outdoors on hot days, per neighborhood. {_NEIGHBORHOODS_FIRST}",
               "Climate", "urban_heat.NeighborhoodHeat", _N),
    _kea_entry("kea_boomkroon_buurt", "RMK_BuurtAggregaties", "Canopy Cover and Shade per Neighborhood (KEA)",
               f"Tree canopy cover and shade (total, from trees, from buildings) as % of the land area, AHN4. {_NEIGHBORHOODS_FIRST}",
               "Climate", "urban_heat.NeighborhoodHeat", _N),
    # ── Housing / demographics: social vulnerability ─────────────────────────
    _kea_entry("kea_huurwoningen", "nl_percentage_huurwoningen_buurt_v20260722", "Rental Dwellings per Neighborhood (KEA)",
               f"Percentage of rental dwellings per neighborhood. {_NEIGHBORHOODS_FIRST}",
               "Housing", "housing.NeighborhoodSocialProfile", _N),
    _kea_entry("kea_sociaal_economische_status", "nl_sociaal_economische_status_buurt_v20260722", "Socio-economic Status per Neighborhood (KEA)",
               f"CBS socio-economic status score (prosperity, education, labour) per neighborhood. {_NEIGHBORHOODS_FIRST}",
               "Demographics", "housing.NeighborhoodSocialProfile", _N),
    _kea_entry("kea_broze_gezondheid", "nl_broze_gezondheid_buurt_v20260722", "Frail Health per Neighborhood (KEA)",
               f"Share of adults with frail health (RIVM health monitor). {_NEIGHBORHOODS_FIRST}",
               "Demographics", "housing.NeighborhoodSocialProfile", _N),
    _kea_entry("kea_sterk_eenzaam", "nl_sterk_eenzaam_buurt_v20260722", "Severe Loneliness per Neighborhood (KEA)",
               f"Share of adults who are severely lonely (RIVM health monitor). {_NEIGHBORHOODS_FIRST}",
               "Demographics", "housing.NeighborhoodSocialProfile", _N),
    _kea_entry("kea_wijktypen", "wijktypen_buurten", "Neighborhood Types (KEA)",
               f"Neighborhood type (e.g. pre-war, post-war, cauliflower, VINEX) per buurt, 2023. {_NEIGHBORHOODS_FIRST}",
               "Demographics", "housing.NeighborhoodSocialProfile", _N),
    # ── Water and nature ─────────────────────────────────────────────────────
    _kea_entry("kea_waterschappen", "Waterschapsgrenzen", "Water Board Boundaries (KEA)",
               "Boundaries of the Dutch water boards (waterschappen), stored as watersheds.",
               "Nature & Environment", "watersupply.Watershed", None),
    _kea_entry("kea_droogtegevoelige_natuur", "droogtegevoeligheidgrondwaterafhankelijkenatuur", "Drought-sensitive Groundwater-dependent Nature (KEA)",
               "Groundwater-dependent nature areas with their drought sensitivity (slightly / sensitive / very sensitive).",
               "Nature & Environment", "watersupply.AreaAffectedDrought", "administrative.Province"),
    _kea_entry("kea_klimaatbuffers", "totaalkaartklimaatbuffers", "Climate Buffers (KEA)",
               "Areas of the national climate-buffer map, stored as protected areas of type Other.",
               "Nature & Environment", "nature.ProtectedArea", None),
]

# Build a quick-lookup dict
CATALOG_BY_KEY = {d["key"]: d for d in EXTERNAL_DATA_CATALOG}

# Sources metadata for the UI
SOURCE_INFO = {
    "pdok": {
        "name": "PDOK",
        "full_name": "Publieke Dienstverlening Op de Kaart",
        "description": "Dutch national geospatial data platform. Open data, no authentication required.",
        "icon": "globe",
        "color": "indigo",
        "auth_required": False,
    },
    
    "CBS":{
      "name": "CBS",
      "full_name": "Census Bureau of Statistics",
      "description": "Dutch national statistics data platform. Open data, no authentication required.",
      "icon": "globe",
      "color": "cyan",
      "auth_required": False 
    },
    
    "sentinel2": {
        "name": "Sentinel-2",
        "full_name": "Copernicus Sentinel-2 Earth Observation",
        "description": "ESA Copernicus satellite imagery. Spectral index/true color datasets run on CDSE's free openEO backend and need an OIDC client id/secret; WCS/WMS layers are open access.",
        "icon": "satellite",
        "color": "violet",
        "auth_required": False,
    },
    "gee": {
        "name": "Google Earth Engine",
        "full_name": "Google Earth Engine",
        "description": "Planetary-scale geospatial analysis platform. Requires a GEE service account JSON key.",
        "icon": "cloud",
        "color": "amber",
        "auth_required": True,
    },

    "knmi": {
        "name": "KNMI",
        "full_name": "Royal Netherlands Meteorological Institute (Data Platform)",
        "description": "Dutch national weather and climate data. The API key is configured on the server (KNMI_API_KEY), so no credentials are asked for here.",
        "icon": "cloud",
        "color": "sky",
        "auth_required": False,
    },

    "bodemdata": {
        "name": "BIS Nederland",
        "full_name": "Bodemkundig Informatiesysteem (WUR, bodemdata.nl)",
        "description": "Dutch soil data maintained by Wageningen Environmental Research. Open WFS data, no authentication required.",
        "icon": "globe",
        "color": "amber",
        "auth_required": False,
    },

    "osm": {
        "name": "OpenStreetMap",
        "full_name": "OpenStreetMap (Overpass API)",
        "description": "Crowd-sourced open map data, fetched through the Overpass API. No authentication required. Data © OpenStreetMap contributors, ODbL.",
        "icon": "globe",
        "color": "emerald",
        "auth_required": False,
    },

    "kea": {
        "name": "Klimaateffectatlas",
        "full_name": "Klimaateffectatlas (climate-effect atlas, Climate Adaptation Services)",
        "description": "Climate-effect maps of the Netherlands (heat, flooding, drought, foundations, social vulnerability) served as an open WFS. No authentication required.",
        "icon": "globe",
        "color": "emerald",
        "auth_required": False,
    },
    "rivm": {
        "name": "RIVM",
        "full_name": "Rijksinstituut voor Volksgezondheid en Milieu",
        "description": "Dutch national institute for public health and the environment. Open WFS data, no authentication required.",
        "icon": "globe",
        "color": "indigo",
        "auth_required": False,
    },
}


def get_catalog_grouped():
    """
    Return the catalog grouped by category.
    Structure: { category: [datasets] }

    Datasets used to also be sub-grouped by source, each with its own
    icon/description sub-header — but with 5 sources spread across a
    category, that added a layer of visual nesting that didn't carry much
    information on its own. The source is still shown, just as a line on
    each dataset row (see importer/views_external.py) instead of a
    structural grouping level.
    """
    grouped = {}
    for ds in EXTERNAL_DATA_CATALOG:
        grouped.setdefault(ds["category"], []).append(ds)
    return grouped