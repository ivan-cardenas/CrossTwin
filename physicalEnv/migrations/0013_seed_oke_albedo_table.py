"""
Seed SurfaceMaterialProperties with Table 5.1 of Oke, T.R., Mills, G.,
Christen, A., Voogt, J.A. (2017), Urban Climates, Cambridge University
Press: "Albedos (alpha) of individual urban and natural materials and of
urban areas. Values given as a range or average" (sources there: Arnfield
1982; Bailey et al. 1997; Bretz et al. 1998; Gubareff et al. 1960; Maykut
1985; Oke 1987, 1988).

`albedo` is the table's average where it gives one (urban, suburban), else
the midpoint of the range. The urban-rural difference rows are not
surfaces and are left out. Thermal properties are not part of the table
and stay empty. Then every land-cover class gets its default material
(physicalEnv/albedo.py) and every polygon without a material the default
of its class.
"""
from django.db import migrations

SOURCE = "Oke et al. (2017) Urban Climates, Table 5.1"

ROUGH = "lower if rough, tilled"
AGITATED = "lower if surface agitated"
SNOW = "depends on crystal structure, density, soiling"
HIGH_REFLECTANCE = "high-reflectance roof materials raise values into 0.4-0.8"

# code, category, name, min, max, average (None: midpoint), note
TABLE_5_1 = [
    # Natural surfaces
    ("soil_dark_wet", "bare_ground", "Soil (dark colour, wet)", 0.05, 0.10, None, ROUGH),
    ("soil_dark_dry", "bare_ground", "Soil (dark colour, dry)", 0.10, 0.13, None, ROUGH),
    ("soil_light_wet", "bare_ground", "Soil (light colour, wet)", 0.12, 0.18, None, ROUGH),
    ("soil_light_dry", "bare_ground", "Soil (light colour, dry)", 0.18, 0.30, None, ROUGH),
    ("desert_sands", "bare_ground", "Desert sands", 0.20, 0.45, None, ROUGH),
    ("grass", "low_vegetation", "Grass", 0.16, 0.26, None, "long -> short"),
    ("crops", "low_vegetation", "Crops", 0.18, 0.25, None, ""),
    ("wetlands", "low_vegetation", "Wetlands", 0.07, 0.19, None, ""),
    ("tundra", "low_vegetation", "Tundra", 0.08, 0.19, None, ""),
    ("forest_deciduous", "forests", "Deciduous", 0.13, 0.20, None, "bare -> leaf"),
    ("orchards", "forests", "Orchards", 0.07, 0.15, None, ""),
    ("forest_coniferous", "forests", "Coniferous", 0.11, 0.13, None, ""),
    ("water_high_sun", "water", "Water (solar altitude > 60°)", 0.03, 0.10, None, AGITATED),
    ("water_low_sun", "water", "Water (solar altitude 10°-60°)", 0.10, 0.50, None, AGITATED),
    ("water_overcast", "water", "Water (overcast)", 0.05, 0.10, None, AGITATED),
    ("snow_fresh", "snow_ice", "Fresh, cold, clean snow", 0.80, 0.90, None, SNOW),
    ("snow_wet", "snow_ice", "Wet, clean snow", 0.50, 0.75, None, SNOW),
    ("snow_old", "snow_ice", "Old, porous, dirty snow", 0.40, 0.50, None, SNOW),
    ("sea_ice_multi_year", "snow_ice", "Sea ice, multi-year", 0.55, 0.75, None, SNOW),
    ("sea_ice_first_year", "snow_ice", "Sea ice, first year", 0.30, 0.60, None, SNOW),
    ("glacier_ice", "snow_ice", "Glacier ice", 0.20, 0.40, None, SNOW),
    # Urban surface materials
    ("road_asphalt", "roads", "Asphalt", 0.05, 0.27, None, "fresh -> weathered"),
    ("road_concrete", "roads", "Concrete", 0.10, 0.35, None, "range due to aggregate and soiling"),
    ("wall_concrete", "walls", "Concrete", 0.10, 0.35, None, "range due to aggregate and soiling"),
    ("wall_brick", "walls", "Brick", 0.20, 0.60, None, "colour, red -> white"),
    ("wall_stone", "walls", "Grey and red stone", 0.20, 0.45, None, ""),
    ("wall_limestone", "walls", "Limestone", 0.40, 0.64, None, ""),
    ("wall_wood", "walls", "Wood", None, None, 0.22, ""),
    ("roof_tile_clay", "roofs", "Tile (clay)", 0.10, 0.35, None, f"old -> fresh; {HIGH_REFLECTANCE}"),
    ("roof_shingles", "roofs", "Shingles", 0.05, 0.25, None, f"dark -> light; {HIGH_REFLECTANCE}"),
    ("roof_tar_gravel_bitumen", "roofs", "Tar and gravel, bitumen", 0.08, 0.18, None, HIGH_REFLECTANCE),
    ("roof_slate", "roofs", "Slate", 0.10, 0.14, None, HIGH_REFLECTANCE),
    ("roof_thatch", "roofs", "Thatch", 0.15, 0.20, None, HIGH_REFLECTANCE),
    ("roof_corrugated_iron", "roofs", "Corrugated iron", 0.10, 0.16, None, HIGH_REFLECTANCE),
    ("roof_galvanized_steel", "roofs", "Galvanized steel", 0.37, 0.45, None, f"weathered -> new; {HIGH_REFLECTANCE}"),
    ("window_clear_glass", "windows", "Clear glass", None, None, 0.08, ""),
    ("window_glass_high_sun", "windows", "Clear glass (solar altitude > 50°)", 0.09, 0.52, None, ""),
    ("window_glass_low_sun", "windows", "Clear glass (solar altitude 10°-50°)", 0.40, 0.80, None, ""),
    ("paint_white", "paints", "White, whitewash", 0.50, 0.90, None, ""),
    ("paint_red_brown_green", "paints", "Red, brown, green", 0.20, 0.35, None, ""),
    ("paint_black", "paints", "Black", 0.02, 0.15, None, ""),
    ("metal_polished", "metals", "Polished metals", 0.50, 0.90, None, ""),
    # Urban areas
    ("urban_snow_free", "urban_areas", "Urban (snow-free)", 0.09, 0.23, 0.14, ""),
    ("urban_with_snow", "urban_areas", "Urban (with snow)", 0.14, 0.41, None, "snow raises values, by less than in the countryside"),
    ("suburban_snow_free", "urban_areas", "Suburban (snow-free)", 0.11, 0.24, 0.15, ""),
]


def seed(apps, schema_editor):
    from physicalEnv.albedo import material_code_for

    Material = apps.get_model("physicalEnv", "SurfaceMaterialProperties")
    Classes = apps.get_model("physicalEnv", "LandCoverClasses")
    LandCoverVector = apps.get_model("physicalEnv", "LandCoverVector")

    by_code = {}
    for code, category, name, lo, hi, average, note in TABLE_5_1:
        albedo = average if average is not None else round((lo + hi) / 2, 3)
        row, _ = Material.objects.update_or_create(code=code, defaults=dict(
            category=category, material_name=name, albedo=albedo, albedo_min=lo, albedo_max=hi,
            note=note, source=SOURCE))
        by_code[code] = row

    for cls in Classes.objects.filter(default_material__isnull=True):
        code = material_code_for(cls.class_name)
        if code in by_code:
            cls.default_material = by_code[code]
            cls.save(update_fields=["default_material"])
            LandCoverVector.objects.filter(land_cover_type=cls, material__isnull=True).update(material=by_code[code])


class Migration(migrations.Migration):

    dependencies = [
        ("physicalEnv", "0012_oke_material_table"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
