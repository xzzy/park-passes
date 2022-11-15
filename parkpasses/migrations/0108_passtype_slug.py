# Generated by Django 3.2.13 on 2022-10-11 06:57

import autoslug.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parkpasses', '0107_alter_retailergroupinvite_initiated_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='passtype',
            name='slug',
            field=autoslug.fields.AutoSlugField(editable=False, null=True, populate_from='display_name', unique=True),
        ),
    ]