"""
ZoningArea.zone_type: free-text category -> FK to physicalEnv.HILUCSLandUse.

Rows that already had one of the old four categories keep it as the closest
HILUCS class (the same groups housing.calculations.calculate_zoning reports).
"""
import django.db.models.deletion
from django.db import migrations, models

OLD_TO_HILUCS = {
    "residential": "5",    # residential use
    "commercial": "3.1",   # commercial services
    "industrial": "2",     # secondary production
    "mixed": "5.2",        # residential use with other compatible uses
}


def to_hilucs(apps, schema_editor):
    ZoningArea = apps.get_model("builtup", "ZoningArea")
    HILUCSLandUse = apps.get_model("physicalEnv", "HILUCSLandUse")
    for old, code in OLD_TO_HILUCS.items():
        ZoningArea.objects.filter(zone_type=old).update(zone_type_hilucs=HILUCSLandUse.objects.get(code=code))


def from_hilucs(apps, schema_editor):
    ZoningArea = apps.get_model("builtup", "ZoningArea")
    for old, code in OLD_TO_HILUCS.items():
        ZoningArea.objects.filter(zone_type_hilucs__code=code).update(zone_type=old)


class Migration(migrations.Migration):

    dependencies = [
        ("builtup", "0004_facility_sourceid_facility_subtype_park_sourceid_and_more"),
        ("physicalEnv", "0003_hilucslanduse"),
    ]

    operations = [
        migrations.AddField(
            model_name="zoningarea",
            name="zone_type_hilucs",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="zoning_areas",
                to="physicalEnv.hilucslanduse",
                help_text="HILUCS land use of the zoning area (INSPIRE planned land use hilucsLandUse), where known",
            ),
        ),
        migrations.RunPython(to_hilucs, from_hilucs),
        migrations.RemoveField(model_name="zoningarea", name="zone_type"),
        migrations.RenameField(model_name="zoningarea", old_name="zone_type_hilucs", new_name="zone_type"),
    ]
