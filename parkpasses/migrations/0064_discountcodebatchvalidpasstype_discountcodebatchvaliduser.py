# Generated by Django 3.2.13 on 2022-08-10 06:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('parkpasses', '0063_pass_drivers_licence_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='DiscountCodeBatchValidUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.IntegerField()),
                ('discount_code_batch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='parkpasses.discountcodebatch')),
            ],
            options={
                'unique_together': {('discount_code_batch', 'user')},
            },
        ),
        migrations.CreateModel(
            name='DiscountCodeBatchValidPassType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('discount_code_batch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='parkpasses.discountcodebatch')),
                ('pass_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='valid_pass_types', to='parkpasses.passtype')),
            ],
            options={
                'unique_together': {('discount_code_batch', 'pass_type')},
            },
        ),
    ]