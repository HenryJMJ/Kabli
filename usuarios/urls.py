from django.urls import path
from . import views
from .views import registro, login_view, logout_view
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin-panel/', views.panel_administrador, name='panel_admin'),
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/editar/<int:usuario_id>/', views.editar_usuario, name='editar_usuario'),
    path('confirmar-eliminar-usuario/<int:usuario_id>/', views.confirmar_eliminar_usuario, name='confirmar_eliminar_usuario'),
    path('usuarios/eliminar/<int:usuario_id>/', views.eliminar_usuario, name='eliminar_usuario'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('academico/', views.gestion_academica, name='gestion_academica'),
    path('recursos/', views.recursos, name='recursos'),
    path('cursos/', views.gestionar_cursos, name='gestionar_cursos'),
    path('cursos/crear/', views.crear_curso, name='crear_curso'),
    path('cursos/editar/', views.editar_cursos, name='editar_cursos'),
    path('cursos/editar/<int:curso_id>/', views.editar_curso, name='editar_curso'),
    path('cursos/eliminar/<int:id>/', views.eliminar_curso, name='eliminar_curso'),
    path('recursos/', views.subir_recursos, name='subir_recursos'),
    path('configuracion/', views.configuracion_admin, name='configuracion'),
    path('mi-perfil/', views.perfil_admin, name='perfil_admin'),
    path('mi-perfil/editar/', views.editar_perfil_admin, name='editar_perfil_admin'),
    path('notificaciones/', views.notificaciones, name='notificaciones'),
    path('notificaciones/eliminar/<int:id>/', views.eliminar_notificacion, name='eliminar_notificacion'),
    path('notificaciones/restaurar/<int:id>/', views.restaurar_notificacion, name='restaurar_notificacion'),
    path('', views.home, name='home'),
    path('registro/', registro, name='registro'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('panel-estudiantes/', views.panel_estudiantes, name='panel_estudiantes'),
    path('perfil/', views.perfil_estudiante, name='perfil_estudiante'),
    path('cursos_disponibles/', views.cursos_disponibles, name='cursos_disponibles'),
    path('panel-docentes/', views.panel_docentes, name='panel_docentes'),
    path('gestionar_cursos/', views.libreria_cursos, name='libreria_cursos'),
    path('libreria_recursos/', views.libreria_recursos, name='libreria_recursos'),
    path('editar_recurso/<int:recurso_id>/', views.editar_recurso, name='editar_recurso'),
    path('eliminar_recurso/<int:recurso_id>/', views.eliminar_recurso, name='eliminar_recurso'),
    path('recurso/<int:recurso_id>/', views.detalle_recurso, name='detalle_recurso'),
    path('estudiantes_curso/', views.estudiantes_curso, name='estudiantes_curso'),
    path('estudiantes/', views.ver_estudiantes, name='ver_estudiantes'),
    path('recuperar/', views.enviar_codigo_view, name='enviar_codigo'),
    path('verificar/', views.verificar_codigo_view, name='verificar_codigo'),
    path('cambiar/', views.cambiar_contraseña_view, name='cambiar_contraseña'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)