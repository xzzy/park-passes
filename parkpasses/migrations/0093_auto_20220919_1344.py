# Generated by Django 3.2.13 on 2022-09-19 05:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('parkpasses', '0092_auto_20220919_1148'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='retailer_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='cart_retailer_group', to='parkpasses.retailergroup'),
        ),
        migrations.AlterField(
            model_name='order',
            name='retailer_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='order_retailer_group', to='parkpasses.retailergroup'),
        ),
    ]
