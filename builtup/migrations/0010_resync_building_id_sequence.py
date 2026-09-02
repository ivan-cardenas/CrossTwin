from django.db import migrations


class Migration(migrations.Migration):
    """
    0007 converted Building.id from a manually-populated BigIntegerField primary key
    to an AutoField via AlterField. Django's AlterField operation changes the column
    type but does not sync the newly-created serial sequence with any pre-existing
    row ids already in the table, so the sequence started back at 1 and collided with
    every existing row ("duplicate key value violates unique constraint
    builtup_building_pkey") until nextval() advanced past them. This resyncs the
    sequence to the table's actual state so new rows never collide with existing ones.
    """

    dependencies = [
        ("builtup", "0009_alter_building_identifier"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SELECT setval('builtup_building_id_seq', COALESCE((SELECT MAX(id) FROM builtup_building), 1), (SELECT MAX(id) IS NOT NULL FROM builtup_building));",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
