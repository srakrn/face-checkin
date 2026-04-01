from django.db import migrations


def _column_names(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    return {column.name for column in description}


def rename_class_id_to_course_id(apps, schema_editor):
    table_name = "checkin_sessions_session"
    columns = _column_names(schema_editor, table_name)
    if "class_id" not in columns or "course_id" in columns:
        return

    quoted_table = schema_editor.quote_name(table_name)
    quoted_old = schema_editor.quote_name("class_id")
    quoted_new = schema_editor.quote_name("course_id")
    schema_editor.execute(f"ALTER TABLE {quoted_table} RENAME COLUMN {quoted_old} TO {quoted_new}")


def rename_course_id_to_class_id(apps, schema_editor):
    table_name = "checkin_sessions_session"
    columns = _column_names(schema_editor, table_name)
    if "course_id" not in columns or "class_id" in columns:
        return

    quoted_table = schema_editor.quote_name(table_name)
    quoted_old = schema_editor.quote_name("course_id")
    quoted_new = schema_editor.quote_name("class_id")
    schema_editor.execute(f"ALTER TABLE {quoted_table} RENAME COLUMN {quoted_old} TO {quoted_new}")


class Migration(migrations.Migration):

    dependencies = [
        ("checkin_sessions", "0004_alter_session_course"),
    ]

    operations = [
        migrations.RunPython(
            rename_class_id_to_course_id,
            reverse_code=rename_course_id_to_class_id,
        ),
    ]
