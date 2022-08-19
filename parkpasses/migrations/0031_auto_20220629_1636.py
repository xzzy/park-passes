# Generated by Django 3.2.13 on 2022-06-29 08:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parkpasses', '0030_auto_20220629_1611'),
    ]

    operations = [
        migrations.AddField(
            model_name='userinformation',
            name='concession_card_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='userinformation',
            name='user',
            field=models.IntegerField(unique=True),
        ),
    ]