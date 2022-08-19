# Generated by Django 3.2.13 on 2022-06-29 08:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parkpasses', '0028_auto_20220629_1503'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='orderitem',
            name='parkpasses__content_ed29ee_idx',
        ),
        migrations.AddField(
            model_name='orderitem',
            name='amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='description',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='orderitem',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='content_type',
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='discount_code',
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='object_id',
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='voucher',
        ),
    ]