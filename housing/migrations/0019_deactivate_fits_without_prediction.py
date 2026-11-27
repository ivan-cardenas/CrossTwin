from django.db import migrations


def deactivate(apps, schema_editor):
    """A fit made before the city-wide equation was stored cannot price a dwelling: none of them stays active."""
    apps.get_model("housing", "PriceModel").objects.filter(isActive=True, prediction={}).update(isActive=False)


class Migration(migrations.Migration):

    dependencies = [
        ("housing", "0018_pricemodel_prediction"),
    ]

    operations = [
        migrations.RunPython(deactivate, migrations.RunPython.noop),
    ]
