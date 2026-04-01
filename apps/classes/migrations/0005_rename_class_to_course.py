from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("classes", "0004_class_owner_class_shared_with_users"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Class",
            new_name="Course",
        ),
        migrations.RenameModel(
            old_name="ClassTag",
            new_name="CourseTag",
        ),
        migrations.RenameField(
            model_name="coursetag",
            old_name="klass",
            new_name="course",
        ),
        migrations.AlterField(
            model_name="course",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="owned_courses",
                to=settings.AUTH_USER_MODEL,
                verbose_name="เจ้าของ",
            ),
        ),
        migrations.AlterField(
            model_name="course",
            name="shared_with_users",
            field=models.ManyToManyField(
                blank=True,
                related_name="shared_courses",
                to=settings.AUTH_USER_MODEL,
                verbose_name="แชร์กับผู้ใช้",
            ),
        ),
        migrations.AlterField(
            model_name="course",
            name="face_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="courses",
                to="faces.facegroup",
                verbose_name="กลุ่มใบหน้า",
            ),
        ),
        migrations.AlterField(
            model_name="coursetag",
            name="course",
            field=models.ForeignKey(
                db_column="course_id",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tags",
                to="classes.course",
                verbose_name="วิชา",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="coursetag",
            unique_together={("course", "tag")},
        ),
        migrations.AlterModelOptions(
            name="course",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "วิชา",
                "verbose_name_plural": "วิชา",
            },
        ),
        migrations.AlterModelOptions(
            name="coursetag",
            options={
                "ordering": ["tag"],
                "verbose_name": "แท็กวิชา",
                "verbose_name_plural": "แท็กวิชา",
            },
        ),
    ]
