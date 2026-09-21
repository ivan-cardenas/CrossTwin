from django.db import migrations


class Migration(migrations.Migration):
    """
    Fix the misspelt field name `price_EUR_price_EUR_droughtDamage_m3`
    (watersupply.ExtractionWater already refers to `price_EUR_droughtDamage_m3`).
    """

    dependencies = [
        ("physicalEnv", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="environmentalcosts",
            old_name="price_EUR_price_EUR_droughtDamage_m3",
            new_name="price_EUR_droughtDamage_m3",
        ),
    ]
