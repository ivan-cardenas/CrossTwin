from django.db import migrations


def deactivate(apps, schema_editor):
    """Fits made before the per-category terms have no termBetas: they can price nothing, so none stays active."""
    apps.get_model("housing", "PriceModel").objects.filter(isActive=True).update(isActive=False)


class Migration(migrations.Migration):

    dependencies = [
        ("housing", "0016_remove_nvm_category_price_terms"),
    ]

    operations = [
        migrations.RunPython(deactivate, migrations.RunPython.noop),
    ]
