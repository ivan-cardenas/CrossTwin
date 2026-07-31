from django.db import migrations

LABEL_DESCRIPTIONS = {
    "A+++": "Most energy efficient; near energy-neutral, minimal primary energy demand.",
    "A++": "Very high energy efficiency, close to energy-neutral performance.",
    "A+": "Very high energy efficiency with low primary energy demand.",
    "A": "High energy efficiency; well-insulated with efficient installations.",
    "B": "Good energy efficiency, above-average performance.",
    "C": "Average energy efficiency, typical of the existing building stock.",
    "D": "Below-average energy efficiency; some improvement potential.",
    "E": "Low energy efficiency; significant improvement potential.",
    "F": "Very low energy efficiency; poor insulation and/or outdated installations.",
    "G": "Least energy efficient; highest primary energy demand, most improvement potential.",
}


def populate_labels(apps, schema_editor):
    EnergyEfficiencyLabels = apps.get_model("Energy", "EnergyEfficiencyLabels")
    for label, description in LABEL_DESCRIPTIONS.items():
        EnergyEfficiencyLabels.objects.get_or_create(
            label=label, defaults={"description": description}
        )


def remove_labels(apps, schema_editor):
    EnergyEfficiencyLabels = apps.get_model("Energy", "EnergyEfficiencyLabels")
    EnergyEfficiencyLabels.objects.filter(label__in=LABEL_DESCRIPTIONS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("Energy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(populate_labels, remove_labels),
    ]
