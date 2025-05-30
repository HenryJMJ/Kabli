# Generated by Django 5.1.2 on 2025-05-20 04:18

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0026_perfil_verificado'),
    ]

    operations = [
        migrations.AddField(
            model_name='curso',
            name='calificacion',
            field=models.FloatField(default=0.0, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(5.0)]),
        ),
        migrations.AddField(
            model_name='curso',
            name='costo',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=8, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))]),
        ),
    ]
