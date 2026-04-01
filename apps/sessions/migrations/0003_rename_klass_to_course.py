from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("classes", "0005_rename_class_to_course"),
        ("checkin_sessions", "0002_add_ip_address_to_checkin"),
    ]

    operations = [
        migrations.RenameField(
            model_name="session",
            old_name="klass",
            new_name="course",
        ),
    ]
