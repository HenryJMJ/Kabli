# Generated by Django 5.1.2 on 2025-05-26 23:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0033_perfil_imagen'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilestudiante',
            name='foto_perfil',
            field=models.ImageField(blank=True, null=True, upload_to='fotos_perfil/'),
        ),
    ]
