from django.db import migrations, models


def populate_shorthand(apps, schema_editor):
    Class = apps.get_model("classes", "Class")
    for klass in Class.objects.all():
        klass.shorthand = klass.name[:50]
        klass.save(update_fields=["shorthand"])


class Migration(migrations.Migration):

    dependencies = [
        ("classes", "0001_initial"),
    ]

    operations = [
        # Add nullable first so existing rows are not blocked
        migrations.AddField(
            model_name="class",
            name="shorthand",
            field=models.CharField(
                max_length=50, unique=True, verbose_name="ชื่อย่อ", null=True
            ),
            preserve_default=False,
        ),
        # Fill in existing rows using the class name
        migrations.RunPython(populate_shorthand, migrations.RunPython.noop),
        # Now enforce NOT NULL and unique
        migrations.AlterField(
            model_name="class",
            name="shorthand",
            field=models.CharField(max_length=50, unique=True, verbose_name="ชื่อย่อ"),
        ),
    ]
