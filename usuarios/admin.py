from django.contrib import admin
from .models import Notificacion

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'fecha', 'usuario')
    search_fields = ('titulo', 'contenido')
    list_filter = ('tipo', 'fecha')
