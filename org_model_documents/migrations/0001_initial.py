# Generated by Django 3.2.13 on 2022-06-14 08:16

from django.db import migrations, models
import django.db.models.deletion
import org_model_documents.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.CharField(help_text='Primary key of the model.', max_length=191)),
                ('_file', models.FileField(upload_to=org_model_documents.models.org_model_document_path)),
                ('datetime_created', models.DateTimeField(auto_now_add=True)),
                ('datetime_updated', models.DateTimeField(auto_now=True)),
                ('content_type', models.ForeignKey(help_text='Content type of the model.', on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['content_type', 'object_id'], name='org_model_d_content_c6406b_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='document',
            unique_together={('content_type', 'object_id')},
        ),
    ]