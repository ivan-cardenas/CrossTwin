"""
Move every builtup.Park row into nature.GreenSpaces with type 'park'
(builtup.Park is deleted by builtup 0013). Parks drawn in the map editor
own green-area land cover through plain ids (physicalEnv LandCoverVector.
source_park, UrbanFabricCut.owner_park / source_park); those ids are
re-pointed to the new GreenSpaces ids. The layer key in the map settings
(editable layers, style overrides) moves from builtup.Park to
nature.GreenSpaces; backup journal rows of builtup.Park are dropped, since
their model no longer exists.
"""
from django.db import migrations

OLD_KEY = "builtup.Park"
NEW_KEY = "nature.GreenSpaces"


def _remap(model, field, mapping):
    """Re-point `field` from old park ids to new green-space ids without collisions (via negative ids)."""
    for old in mapping:
        model.objects.filter(**{field: old}).update(**{field: -old - 1})
    for old, new in mapping.items():
        model.objects.filter(**{field: -old - 1}).update(**{field: new})


def move_parks(apps, schema_editor):
    Park = apps.get_model("builtup", "Park")
    GreenSpaces = apps.get_model("nature", "GreenSpaces")
    Neighborhood = apps.get_model("administrative", "Neighborhood")
    City = apps.get_model("administrative", "City")

    mapping = {}
    for park in Park.objects.all().iterator():
        city_id = None
        if park.neighborhood_id:
            city_id = (Neighborhood.objects.filter(pk=park.neighborhood_id)
                       .values_list("district__city_id", flat=True).first())
        if city_id is None and park.geom:
            city_id = City.objects.filter(geom__contains=park.geom.centroid).values_list("pk", flat=True).first()
        green = None
        if park.sourceID:
            green = GreenSpaces.objects.filter(sourceID=park.sourceID).first()
        if green is None:
            green = GreenSpaces(sourceID=park.sourceID)
        green.name = park.name
        green.type = "park"
        green.vegetationType = park.vegetationType
        green.neighborhood_id = park.neighborhood_id
        green.city_id = city_id
        green.geom = park.geom
        green.area = park.geom.area if park.geom else park.area
        green.save()
        mapping[park.pk] = green.pk

    LandCoverVector = apps.get_model("physicalEnv", "LandCoverVector")
    UrbanFabricCut = apps.get_model("physicalEnv", "UrbanFabricCut")
    if mapping:
        _remap(LandCoverVector, "source_park", mapping)
        _remap(UrbanFabricCut, "owner_park", mapping)
        _remap(UrbanFabricCut, "source_park", mapping)

    EditableLayer = apps.get_model("mainMap", "EditableLayer")
    if EditableLayer.objects.filter(key=OLD_KEY).exists():
        EditableLayer.objects.filter(key=OLD_KEY).delete()
        EditableLayer.objects.get_or_create(key=NEW_KEY)
    LayerStyleOverride = apps.get_model("mainMap", "LayerStyleOverride")
    for override in LayerStyleOverride.objects.filter(kind="vector", key=OLD_KEY):
        if LayerStyleOverride.objects.filter(kind="vector", key=NEW_KEY).exists():
            override.delete()
        else:
            override.key = NEW_KEY
            override.save(update_fields=["key"])
    apps.get_model("mainMap", "EditBackupRow").objects.filter(layer_key=OLD_KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("nature", "0003_greenspaces_parks"),
        ("builtup", "0012_degree_of_urbanisation"),
        ("physicalEnv", "0015_greenspaces_parks"),
        ("mainMap", "0002_map_settings"),
    ]

    operations = [
        migrations.RunPython(move_parks, migrations.RunPython.noop),
    ]
