from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("Energy", "0002_populate_energy_labels"),
        ("builtup", "0016_building_energy_label_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="BuildingEnergyLabel",
            fields=[],
            options={
                "verbose_name": "Building Energy Label",
                "verbose_name_plural": "Building Energy Labels",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("builtup.building",),
        ),
    ]
