from .models import Notificacion

def notificaciones_context(request):
    if request.user.is_authenticated:
        notificaciones = Notificacion.objects.filter(
            usuario_afectado=request.user,
            visto=False
        )
        cantidad_no_vistas = notificaciones.count()
        return {
            'notificaciones_no_vistas': cantidad_no_vistas,
            'hay_notificaciones': cantidad_no_vistas > 0,
        }
    return {
        'notificaciones_no_vistas': 0,
        'hay_notificaciones': False,
    }
