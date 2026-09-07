from django.db import migrations, models

_ENERGY_LABEL_CHOICES = [
    ("A+++", "A+++"),
    ("A++", "A++"),
    ("A+", "A+"),
    ("A", "A"),
    ("B", "B"),
    ("C", "C"),
    ("D", "D"),
    ("E", "E"),
    ("F", "F"),
    ("G", "G"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("builtup", "0015_alter_building_usagefunction"),
    ]

    operations = [
        migrations.AlterField(
            model_name="building",
            name="energyLabel",
            field=models.CharField(
                blank=True,
                choices=_ENERGY_LABEL_CHOICES,
                help_text="Dominant registered energy label for this building (RVO EP-Online register, via RIVM's rvo_energielabels WFS)",
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="building",
            name="energyLabelHighest",
            field=models.CharField(
                blank=True,
                choices=_ENERGY_LABEL_CHOICES,
                help_text="Best registered label among this building's units (RVO EP-Online register, via RIVM's rvo_energielabels WFS)",
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="building",
            name="energyLabelLowest",
            field=models.CharField(
                blank=True,
                choices=_ENERGY_LABEL_CHOICES,
                help_text="Worst registered label among this building's units (RVO EP-Online register, via RIVM's rvo_energielabels WFS)",
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="building",
            name="energyLabelCount",
            field=models.IntegerField(
                blank=True,
                help_text="Number of registered energy labels found for this building (RVO EP-Online register, via RIVM's rvo_energielabels WFS)",
                null=True,
            ),
        ),
    ]
