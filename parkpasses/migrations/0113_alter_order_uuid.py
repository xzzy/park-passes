# Generated by Django 3.2.13 on 2022-10-17 07:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parkpasses', '0112_auto_20221017_1445'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='uuid',
            field=models.CharField(help_text='This is copied from the cart to the order before the cart is deleted.             It is also stored in ledger as the booking reference of the basket.', max_length=36, unique=True),
        ),
    ]
