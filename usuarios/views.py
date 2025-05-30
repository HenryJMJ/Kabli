from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.mail import EmailMessage
from django.db import IntegrityError
from .forms import RegistroForm
from django.conf import settings
from django.core.mail import send_mail
from .models import PasswordResetCode, User
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.timezone import localtime
from django.contrib.auth.models import Group
from .models import Perfil
import json
import os
from datetime import date
from django.db.models import Count
from django.db.models.functions import TruncDate
from collections import defaultdict
from usuarios.models import Notificacion
from .models import Notificacion
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from .models import Curso, Unidad, Sesion, CalificacionCurso, SesionCompletada, Categoria
from .models import CursoDocente
from .models import CursoInscrito
from .models import PerfilEstudiante
from .forms import CursoForm
from .models import Recurso
from .forms import RecursoForm
from .forms import MensajeForm, UnidadForm, SesionForm, CalificacionForm
from django.db.models import Avg


def home(request):
    return render(request, 'usuarios/home.html')

def es_superusuario(user):
    return user.is_superuser or user.is_staff

@login_required
@user_passes_test(es_superusuario)
def panel_administrador(request):
    show_welcome = False

    if not request.session.get('welcome_shown', False):
        request.session['welcome_shown'] = True
        show_welcome = True

    usuarios = User.objects.all().exclude(username=request.user.username)

    # Contar notificaciones no vistas
    notificaciones_no_vistas = Notificacion.objects.filter(usuario_afectado=request.user, visto=False).count()

    return render(request, 'usuarios/panel_admin.html', {
        'usuarios': usuarios,
        'show_welcome': show_welcome,
        'notificaciones_no_vistas': notificaciones_no_vistas
    })

@login_required
def inicio_admin(request):
    return render(request, 'usuarios/inicio.html')

def lista_usuarios(request):
    usuarios = User.objects.all()
    return render(request, 'lista_usuarios.html', {'usuarios': usuarios})

def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(User, pk=usuario_id)
    
    if request.method == 'POST':
        nuevo_username = request.POST.get('username', '').strip()
        nuevo_email = request.POST.get('email', '').strip()

        # Validación: al menos uno debe estar lleno
        if not nuevo_username and not nuevo_email:
            messages.error(request, 'Debes ingresar al menos un dato para actualizar.')
        else:
            if nuevo_username:
                usuario.username = nuevo_username
            if nuevo_email:
                usuario.email = nuevo_email

            usuario.save()
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('lista_usuarios')
    
    return render(request, 'usuarios/editar_usuario.html', {'usuario': usuario})

def confirmar_eliminar_usuario(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)
    return render(request, 'usuarios/confirmar_eliminar_usuario.html', {'usuario': usuario})

def eliminar_usuario(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)
    usuario.delete()
    return redirect('lista_usuarios')

def estadisticas(request):
    usuarios = User.objects.exclude(is_superuser=True)  # Excluir admin

    docentes = usuarios.filter(groups__name='docente')
    estudiantes = usuarios.filter(groups__name='estudiante')

    total_docentes = docentes.count()
    total_estudiantes = estudiantes.count()
    total_usuarios = total_docentes + total_estudiantes

    contexto = {
        'usuarios': usuarios,
        'docentes': docentes,
        'estudiantes': estudiantes,
        'total_usuarios': total_usuarios,
        'total_docentes': total_docentes,
        'total_estudiantes': total_estudiantes,
    }
    return render(request, 'usuarios/estadisticas.html', contexto)

def recursos(request):
    return render(request, 'usuarios/recursos.html')

def configuracion_admin(request):
    return render(request, 'usuarios/configuracion.html')

def perfil_admin(request):
    return render(request, 'usuarios/perfil_admin.html')

@login_required
def editar_perfil_admin(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.username = request.POST.get('username', '')
        user.save()
        return redirect('perfil_admin')
    return render(request, 'usuarios/editar_perfil_admin.html')

@csrf_exempt  # Puedes quitarlo si ya estás usando CSRF desde JS
def restaurar_notificacion(request, id):
    if request.method == 'POST':
        notificacion = get_object_or_404(Notificacion, id=id)
        notificacion.eliminada = False
        notificacion.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

def registro(request):
    categorias = Categoria.objects.all()

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                rol = form.cleaned_data['rol']

                # Activar usuario según rol
                if rol == 'docente':
                    user.is_active = False  # Docente debe verificar su cuenta
                else:
                    user.is_active = True   # Estudiante activo por defecto

                user.save()

                # Asignar grupo al usuario
                grupo, _ = Group.objects.get_or_create(name=rol)
                user.groups.add(grupo)

                # Crear perfil según rol
                if rol == 'docente':
                    especialidad_id = request.POST.get('especialidad')
                    if not especialidad_id:
                        messages.error(request, "Debes seleccionar una especialidad para docentes.")
                        # Opcional: eliminar usuario creado si quieres evitar usuarios sin perfil válido
                        user.delete()
                        return redirect('registro')

                    categoria = Categoria.objects.get(id=especialidad_id)

                    Perfil.objects.create(
                        usuario=user,
                        rol='docente',
                        categoria=categoria
                    )

                    enviar_correo_verificacion_docente(user)

                elif rol == 'estudiante':
                    Perfil.objects.create(usuario=user, rol='estudiante')
                    PerfilEstudiante.objects.create(usuario=user)

                # Crear notificación para administrador (usuario 'Kabli')
                admin_user = User.objects.filter(username='Kabli').first()
                if admin_user:
                    Notificacion.objects.create(
                        titulo="Nuevo registro de usuario",
                        contenido=f"Se ha registrado a {user.first_name} {user.last_name} con el rol de {rol.capitalize()}.",
                        tipo='info',
                        usuario=user,
                        usuario_afectado=admin_user,
                        visto=False
                    )

                messages.success(request, "Registro exitoso. Inicia sesión.")
                return redirect('registro')

            except IntegrityError:
                messages.error(request, "Hubo un error al crear el usuario. Intenta de nuevo.")
                return redirect('registro')

            except Exception as e:
                messages.error(request, f"Error inesperado: {e}")
                return redirect('registro')

        else:
            messages.error(request, "Corrige los errores a continuación.")
    else:
        form = RegistroForm()

    return render(request, 'usuarios/registro.html', {
        'form': form,
        'categorias': categorias
    })

def enviar_correo_verificacion_docente(user):
    asunto = "Verificación de cuenta como docente"
    mensaje = f"""
Hola {user.first_name},

Gracias por registrarte como docente en nuestra plataforma.

Tu cuenta será revisada por nuestros administradores para verificar si calificas. 
Este proceso puede tardar de 10 minutos a 1 hora.

Te notificaremos por correo una vez sea aceptada o rechazada.

Gracias por tu interés.

Atentamente,
El equipo académico.
"""
    send_mail(asunto, mensaje, settings.DEFAULT_FROM_EMAIL, [user.email])

def verificar_docente(request):
    docentes_pendientes = User.objects.filter(perfil__rol='docente', is_active=False).select_related('perfil__categoria')
    return render(request, 'usuarios/verificar_docente.html', {'docentes': docentes_pendientes})


def verificar_docente_accion(request, user_id, accion):
    try:
        # Obtener al docente que tiene el rol de 'docente'
        docente = User.objects.get(id=user_id, perfil__rol='docente')

        if accion == 'aceptar':
            # Activar la cuenta del docente
            docente.is_active = True
            docente.save()

            # Enviar correo notificando que la cuenta ha sido aceptada
            send_mail(
                subject="Acceso aprobado",
                message=f"Felicidades docente {docente.username}, ya puedes acceder a tu cuenta.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[docente.email],
                fail_silently=True
            )
            messages.success(request, f"{docente.username} ha sido verificado correctamente.")
        
        elif accion == 'rechazar':
            # Enviar correo notificando que la cuenta ha sido rechazada
            send_mail(
                subject="Acceso denegado",
                message="Lo lamentamos, pero no has calificado. Puedes intentarlo en otra convocatoria.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[docente.email],
                fail_silently=True
            )

            # Eliminar al docente de la base de datos
            docente.delete()
            messages.info(request, f"{docente.username} ha sido rechazado y eliminado.")

        else:
            messages.error(request, "Acción no válida. No se puede procesar la solicitud.")

    except User.DoesNotExist:
        messages.error(request, "El usuario no existe o no es un docente válido.")

    return redirect('verificar_docente')

def lista_usuarios(request):
    query = request.GET.get("q")
    rol = request.GET.get("rol")

    usuarios = User.objects.all().select_related('perfil')  # Para evitar múltiples consultas a Perfil

    if query:
        usuarios = usuarios.filter(username__icontains=query)

    if rol:
        if rol == 'administracion':
            usuarios = usuarios.filter(is_superuser=True)
        else:
            usuarios = usuarios.filter(perfil__rol=rol)

    context = {
        'usuarios': usuarios
    }
    return render(request, 'usuarios/lista_usuarios.html', context)

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                # Autenticación Django
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    # Si es superuser o staff, no necesita perfil
                    if user.is_superuser or user.is_staff:
                        login(request, user)
                        return redirect('panel_admin')

                    # Si no es superuser, validamos perfil
                    try:
                        perfil = user.perfil

                        if perfil.rol == 'docente' and not user.is_active:
                            messages.warning(request, 'Tu cuenta como docente está pendiente de verificación. Espera a ser aprobado.')
                            return render(request, 'usuarios/login.html')

                        login(request, user)
                        if perfil.rol == 'docente':
                            return redirect('panel_docentes')
                        elif perfil.rol == 'estudiante':
                            return redirect('panel_estudiantes')
                        else:
                            messages.error(request, 'Tu rol no tiene acceso asignado.')
                            return redirect('login')

                    except Perfil.DoesNotExist:
                        messages.error(request, 'Tu cuenta no tiene un perfil asignado.')
                        return redirect('login')
                else:
                    messages.error(request, 'Usuario o contraseña incorrectos.')
            else:
                messages.error(request, 'Usuario o contraseña incorrectos.')
        except User.DoesNotExist:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'usuarios/login.html')

@login_required
def panel_estudiantes(request):
    if request.user.perfil.rol != 'estudiante':
        return redirect('login')  # o redirige a su panel correspondiente

    nombre = request.user.first_name or request.user.username
    return render(request, 'usuarios/panel_estudiantes.html', {'nombre_usuario': nombre})

@login_required
def academica(request):
    # Todas las inscripciones del estudiante con info relacionada
    cursos_inscritos = CursoInscrito.objects.filter(estudiante=request.user).select_related(
        'curso_docente__curso', 'curso_docente__docente'
    )

    # IDs de cursos que ya fueron pagados (al menos en una inscripción)
    cursos_pagados_ids = CursoInscrito.objects.filter(
        estudiante=request.user,
        pagado=True
    ).values_list('curso_docente__curso__id', flat=True).distinct()

    # Construir lista con inscripcion + flag curso_ya_pagado
    cursos_con_estado = []
    for inscripcion in cursos_inscritos:
        curso_ya_pagado = inscripcion.curso_docente.curso.id in cursos_pagados_ids
        cursos_con_estado.append({
            'inscripcion': inscripcion,
            'curso_ya_pagado': curso_ya_pagado
        })

    # Filtrar las inscripciones que no están pagadas para el botón pagar todos
    cursos_no_pagados = cursos_inscritos.filter(pagado=False)

    return render(request, 'usuarios/academica.html', {
        'cursos_inscritos': cursos_con_estado,
        'cursos_no_pagados': cursos_no_pagados
    })

@login_required
def darse_de_baja(request, inscripcion_id):
    inscripcion = get_object_or_404(CursoInscrito, id=inscripcion_id, estudiante=request.user)

    if request.method == 'POST':
        curso = inscripcion.curso_docente
        docente = curso.docente
        nombre_curso = curso.curso.nombre

        inscripcion.delete()
        messages.success(request, "Te has dado de baja del curso exitosamente.")

        # Notificación al docente
        Notificacion.objects.create(
            titulo="Estudiante se dio de baja",
            contenido=f"{request.user.username} se ha dado de baja del curso '{nombre_curso}'.",
            tipo="mensaje",
            usuario=request.user,
            usuario_afectado=docente
        )

        # Notificación al estudiante
        Notificacion.objects.create(
            titulo="Te diste de baja del curso",
            contenido=f"Has cancelado tu inscripción en el curso '{nombre_curso}'.",
            tipo="advertencia",
            usuario=request.user,
            usuario_afectado=request.user
        )

        return redirect('academica')

    messages.error(request, "Ocurrió un error al intentar darte de baja.")
    return redirect('academica')

@login_required
def enviar_mensaje(request):
    if request.method == 'POST':
        form = MensajeForm(request.POST)
        if form.is_valid():
            asunto = form.cleaned_data['asunto']
            mensaje = form.cleaned_data['mensaje']
            email_usuario = request.user.email
            nombre_usuario = request.user.get_full_name() or request.user.username

            cuerpo_mensaje = (
                f"Mensaje enviado por: {nombre_usuario} ({email_usuario})\n\n"
                f"{mensaje}"
            )

            email = EmailMessage(
                subject=asunto,
                body=cuerpo_mensaje,
                from_email='no-responder@tudominio.com',
                to=['henrymestra16@gmail.com'],
                reply_to=[email_usuario],
            )
            email.send(fail_silently=False)

            return render(request, 'usuarios/mensaje_enviado.html')  # redirige a plantilla de éxito
    else:
        form = MensajeForm()

    return render(request, 'usuarios/enviar_mensaje.html', {'form': form})

@login_required
def chatbot_view(request):
    return render(request, 'usuarios/chatbot.html')

@login_required
def mensaje_enviado(request):
    return render(request, 'usuarios/mensaje_enviado.html')

from django.db.models import Q

@login_required
def cursos_disponibles(request):
    query = request.GET.get('q', '')
    categoria_id = request.GET.get('categoria', '')

    # Cursos publicados (inicial)
    cursos_publicados = CursoDocente.objects.filter(publicado=True)

    # Búsqueda por nombre del curso
    if query:
        cursos_publicados = cursos_publicados.filter(
            Q(curso__nombre__icontains=query)
        )

    # Filtro por categoría
    if categoria_id.isdigit():
        cursos_publicados = cursos_publicados.filter(
            curso__categoria__id=categoria_id
        )

    # Lista de cursos con información adicional (estado de inscripción)
    cursos_con_estado = []
    for curso_docente in cursos_publicados:
        descripcion_palabras = curso_docente.curso.descripcion.split(' ')
        esta_inscrito = CursoInscrito.objects.filter(
            estudiante=request.user, curso_docente=curso_docente
        ).exists()

        cursos_con_estado.append({
            'curso': curso_docente,
            'inscrito': esta_inscrito,
            'descripcion_palabras': descripcion_palabras,
        })

    # Cursos en los que ya está inscrito el usuario
    inscritos_ids = CursoInscrito.objects.filter(
        estudiante=request.user
    ).values_list('curso_docente_id', flat=True)

    # Recomendaciones: cursos al azar no inscritos
    recomendados = CursoDocente.objects.filter(publicado=True)\
        .exclude(id__in=inscritos_ids)\
        .order_by('?')[:5]

    # Populares: cursos con más inscritos
    populares = CursoDocente.objects.filter(publicado=True)\
        .annotate(num_estudiantes=Count('cursoinscrito'))\
        .order_by('-num_estudiantes')[:3]

    categorias = Categoria.objects.all()

    return render(request, 'usuarios/cursos_disponibles.html', {
        'cursos_con_estado': cursos_con_estado,
        'query': query,
        'categorias': categorias,
        'categoria_filtrada': categoria_id,
        'recomendados': recomendados,
        'populares': populares,
    })

    
@login_required
def publicar_curso(request, curso_id):
    # Busca la relación entre el curso y el docente
    try:
        curso_docente = CursoDocente.objects.get(curso__id=curso_id, docente=request.user)
    except CursoDocente.DoesNotExist:
        messages.error(request, "No se encontró el curso o no eres el docente de este curso.")
        return redirect('panel_docentes')

    # Publica el curso
    curso_docente.publicado = True
    curso_docente.save()
    
    messages.success(request, 'Curso publicado con éxito.')
    return redirect('curso_docente')  # O el nombre de la vista que muestra los cursos del docente

@login_required
def despublicar_curso(request, curso_id):
    curso_docente = get_object_or_404(CursoDocente, docente=request.user, curso__id=curso_id)
    curso_docente.publicado = False
    curso_docente.save()
    return redirect('curso_docente')

@login_required
def detalle_curso(request, id):
    # Obtener el curso docente publicado o lanzar 404
    curso_docente = get_object_or_404(CursoDocente, id=id, publicado=True)
    curso = curso_docente.curso
    docente = curso_docente.docente

    estudiante = request.user
    # Comprobar si el usuario ya está inscrito en este curso docente
    ya_inscrito = CursoInscrito.objects.filter(estudiante=estudiante, curso_docente=curso_docente).exists()

    context = {
        'curso_docente': curso_docente,
        'curso': curso,
        'docente': docente,
        'ya_inscrito': ya_inscrito,
    }
    return render(request, 'usuarios/detalle_curso.html', context)

@login_required
def inscribir_curso(request, curso_docente_id):
    curso_docente = get_object_or_404(CursoDocente, id=curso_docente_id)
    curso = curso_docente.curso

    if request.method == 'POST':
        if CursoInscrito.objects.filter(curso_docente=curso_docente, estudiante=request.user).exists():
            return render(request, 'usuarios/ya_inscrito.html')

        # Crear inscripción
        CursoInscrito.objects.create(curso_docente=curso_docente, estudiante=request.user)

        # Notificación al docente
        Notificacion.objects.create(
            titulo="Nuevo estudiante inscrito",
            contenido=f"{request.user.username} se ha inscrito en tu curso '{curso.nombre}'.",
            tipo='info',
            usuario=request.user,
            usuario_afectado=curso_docente.docente
        )

        # Notificación al estudiante
        Notificacion.objects.create(
            titulo="Te has inscrito en un curso",
            contenido=f"Te has inscrito correctamente en el curso '{curso.nombre}'.",
            tipo='info',
            usuario=request.user,
            usuario_afectado=request.user
        )

        messages.success(request, "¡Inscripción exitosa!")
        return redirect('cursos_disponibles')

    return render(request, 'usuarios/inscribir_curso.html', {'curso': curso_docente})

@login_required
def estudiantes_curso(request):
    cursos_publicados = CursoDocente.objects.filter(docente=request.user, publicado=True)
    inscripciones = CursoInscrito.objects.filter(
        curso_docente__in=cursos_publicados
    ).select_related('estudiante', 'curso_docente__curso', 'estudiante__perfilestudiante')  # Traemos perfil

    cursos_con_estudiantes = defaultdict(list)

    for inscripcion in inscripciones:
        curso_nombre = inscripcion.curso_docente.curso.nombre

        perfil = getattr(inscripcion.estudiante, 'perfilestudiante', None)
        if perfil and perfil.foto_perfil:
            foto_url = perfil.foto_perfil.url
        else:
            foto_url = None  # Luego en la plantilla mostramos la por defecto

        estudiante_info = {
            'nombre': inscripcion.estudiante.get_full_name() or inscripcion.estudiante.username,
            'fecha': inscripcion.fecha_inscripcion.strftime('%d/%m/%Y %H:%M'),
            'pagado': inscripcion.pagado,
            'foto_perfil_url': foto_url,
        }
        cursos_con_estudiantes[curso_nombre].append(estudiante_info)

    return render(request, 'usuarios/estudiantes_curso.html', {
        'cursos_con_estudiantes': dict(cursos_con_estudiantes),
        'media_url': settings.MEDIA_URL,
    })

@login_required
def perfil_estudiante(request):
    perfil_estudiante, created = PerfilEstudiante.objects.get_or_create(usuario=request.user)

    if request.method == "POST":
        # Si el usuario hizo clic en "Eliminar Imagen"
        if request.POST.get('accion') == 'eliminar_imagen':
            if perfil_estudiante.foto_perfil:
                # Borrar el archivo físicamente
                if os.path.isfile(perfil_estudiante.foto_perfil.path):
                    os.remove(perfil_estudiante.foto_perfil.path)
                perfil_estudiante.foto_perfil = None
                perfil_estudiante.save()
                messages.success(request, "Imagen eliminada correctamente.")
            else:
                messages.error(request, "No hay imagen para eliminar.")
            return redirect('perfil_estudiante')

        # Si el usuario actualizó el perfil
        request.user.first_name = request.POST.get('nombre', "")
        request.user.email = request.POST.get('correo', "")
        
        perfil_estudiante.identificacion = request.POST.get('identificacion', "")
        edad = request.POST.get('edad', "")
        perfil_estudiante.edad = int(edad) if edad else None
        perfil_estudiante.telefono = request.POST.get('telefono', "")
        perfil_estudiante.departamento = request.POST.get('departamento', "")
        perfil_estudiante.ciudad = request.POST.get('ciudad', "")

        if 'foto_perfil' in request.FILES:
            # Si ya había una imagen anterior, eliminarla primero
            if perfil_estudiante.foto_perfil and os.path.isfile(perfil_estudiante.foto_perfil.path):
                os.remove(perfil_estudiante.foto_perfil.path)
            perfil_estudiante.foto_perfil = request.FILES['foto_perfil']

        try:
            request.user.save()
            perfil_estudiante.save()
            messages.success(request, "¡Perfil actualizado correctamente!")
        except Exception as e:
            messages.error(request, f"Hubo un error al actualizar el perfil: {e}")

        return redirect('perfil_estudiante')

    return render(request, 'usuarios/perfil_estudiante.html', {
        'usuario': request.user,
        'perfil_estudiante': perfil_estudiante
    })

@login_required
def panel_docentes(request):
    try:
        if request.user.perfil.rol != 'docente':
            return redirect('login')
    except Perfil.DoesNotExist:
        return redirect('login')

    recursos = Recurso.objects.filter(docente=request.user)

    notificaciones_no_vistas = Notificacion.objects.filter(
        usuario_afectado=request.user,
        eliminada=False,
        visto=False
    ).count()

    return render(request, 'usuarios/panel_docentes.html', {
        'recursos': recursos,
        'notificaciones_no_vistas': notificaciones_no_vistas
    })

@login_required
def libreria_cursos(request):
    usuario = request.user

    try:
        categoria_docente = usuario.perfil.categoria
    except Perfil.DoesNotExist:
        categoria_docente = None

    # Filtrar los cursos por la categoría del docente
    if categoria_docente:
        cursos = Curso.objects.filter(categoria=categoria_docente)
    else:
        cursos = Curso.objects.none()  # No mostrar nada si no tiene categoría

    # Verificar cursos ya agregados por este docente
    cursos_asignados = CursoDocente.objects.filter(docente=usuario)

    for curso in cursos:
        curso.agregado = CursoDocente.objects.filter(curso=curso, docente=usuario).exists()
        curso.cursos_asignados = CursoDocente.objects.filter(curso=curso).count()
        curso.completado = curso.unidades_completadas >= curso.total_unidades if hasattr(curso, 'unidades_completadas') else False

    return render(request, 'usuarios/libreria_cursos.html', {
        'cursos': cursos,
    })

@login_required
def agregar_curso_docente(request, curso_id):
    if request.method == 'POST':
        usuario = request.user
        curso = get_object_or_404(Curso, id=curso_id)

        # Verificar si el docente ya tiene el curso asignado
        if CursoDocente.objects.filter(curso=curso, docente=usuario).exists():
            return JsonResponse({'mensaje': 'Este curso ya fue agregado.', 'exito': False})

        # Verificar si el curso tiene 3 docentes asignados
        if CursoDocente.objects.filter(curso=curso).count() >= 3:
            return JsonResponse({'mensaje': 'El curso ya está completo. No se pueden agregar más docentes.', 'exito': False})

        # Verifica cuántos cursos tiene asignados el docente
        if CursoDocente.objects.filter(docente=usuario).count() >= 2:
            return JsonResponse({'mensaje': 'Ya tienes el máximo de dos cursos asignados.', 'exito': False})

        # Asigna el curso al docente
        CursoDocente.objects.create(curso=curso, docente=usuario)

        # Actualiza el curso específico
        cursos_asignados = CursoDocente.objects.filter(curso=curso).count()

        return JsonResponse({
            'mensaje': 'Curso agregado a tu sección de cursos',
            'exito': True,
            'cursos_asignados': cursos_asignados  # Enviar la cantidad de cursos asignados solo para ese curso
        })

    return JsonResponse({'mensaje': 'Método no permitido', 'exito': False}, status=405)

@login_required
def curso_docente(request):
    cursos_asignados = CursoDocente.objects.filter(docente=request.user).select_related('curso')
    return render(request, 'usuarios/curso_docente.html', {'cursos': cursos_asignados})

@login_required
def eliminar_curso_docente(request, curso_id):
    # Eliminar la relación entre el docente y el curso
    CursoDocente.objects.filter(curso_id=curso_id, docente=request.user).delete()
    return redirect('curso_docente')

@login_required
def subir_recursos(request):
    return render(request, 'usuarios/recursos.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'Has cerrado sesión')
    return redirect('login')

def enviar_codigo_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()
        if user:
            code_instance = PasswordResetCode.objects.create(user=user)
            send_mail(
                'Código de Verificación',
                f'¡Hola!\n\n'
                f'\n\n'
                f'Este es tu código de verificación para recuperar tu contraseña: {code_instance.code}\n\n'
                f'\n\n'
                f'Ingresa el código correctamente para poder cambiar tu contraseña 🔑.\n\n'
                f'\n\n'
                f'⚠️ IMPORTANTE:\n\n'
                f'• Este código es único y tiene un tiempo limitado para su uso ⏳.\n\n'
                f'• No compartas tu código con nadie por seguridad 🔒.\n\n'
                f'\n\n'
                f'Si no solicitaste este código, por favor ignora este mensaje 🛑.\n\n'
                f'\n\n'
                f'¡Gracias por utilizar nuestros servicios! 🙏\n\n'
                f'\n\n'
                f'Saludos,\n\n'
                f' El equipo de soporte.',
                settings.DEFAULT_FROM_EMAIL,
                [email]
            )
            request.session['reset_user_id'] = user.id
            messages.success(request, 'Se ha enviado un código a tu correo, verifica en ingrésalo aquí')
            return redirect('verificar_codigo')
        else:
            messages.error(request, 'No existe una cuenta con ese correo.')
    return render(request, 'usuarios/enviar_codigo.html')

def verificar_codigo_view(request):
    if request.method == 'POST':
        codigo = request.POST.get('codigo')
        user_id = request.session.get('reset_user_id')

        if not user_id:
            messages.error(request, 'La sesión ha expirado. Por favor, solicita un nuevo código.')
            return redirect('enviar_codigo')

        user = get_object_or_404(User, id=user_id)

        # Busca el código más reciente que no se haya usado
        codigo_instancia = PasswordResetCode.objects.filter(
            user=user,
            code=codigo,
            is_used=False
        ).last()

        # Verifica si el código existe y es válido
        if codigo_instancia and codigo_instancia.is_valid():
            codigo_instancia.is_used = True
            codigo_instancia.save()

            # Marca la sesión como validada
            request.session['codigo_validado'] = True
            return redirect('cambiar_contraseña')
        else:
            messages.error(request, 'El código es inválido o ha expirado.')

    return render(request, 'usuarios/verificar_codigo.html')

def cambiar_contraseña_view(request):
    if not request.session.get('codigo_validado'):
        return redirect('enviar_codigo')

    if request.method == 'POST':
        nueva = request.POST.get('nueva')
        confirmar = request.POST.get('confirmar')
        if nueva == confirmar:
            user = User.objects.get(id=request.session['reset_user_id'])
            user.password = make_password(nueva)
            user.save()
            messages.success(request, 'Contraseña actualizada con éxito.')
            request.session.flush()
            return redirect('login')
        else:
            messages.error(request, 'Las contraseñas no coinciden.')
    return render(request, 'usuarios/cambiar_contraseña.html')

@login_required
def gestionar_cursos(request):
    cursos = Curso.objects.all()
    return render(request, 'usuarios/cursos.html', {'cursos': cursos})

@login_required
def crear_curso(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        imagen = request.FILES.get('imagen')
        costo = request.POST.get('costo', 0)
        categoria_id = request.POST.get('categoria')

        categoria = Categoria.objects.get(id=categoria_id) if categoria_id else None

        curso = Curso.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            imagen=imagen,
            costo=costo,
            calificacion=0.0,
            categoria=categoria
        )

        docentes = request.POST.getlist('docentes')
        for docente_id in docentes:
            try:
                docente = User.objects.get(id=docente_id)
                CursoDocente.objects.create(curso=curso, docente=docente)
            except User.DoesNotExist:
                continue

        return redirect('gestionar_cursos')

    categorias = Categoria.objects.all()
    return render(request, 'usuarios/crear_curso.html', {
        'categorias': categorias
    })
@login_required
def editar_cursos(request):
    cursos = Curso.objects.all()
    return render(request, 'usuarios/editar_cursos.html', {'cursos': cursos})

@login_required
def editar_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)

    if request.method == 'POST':
        form = CursoForm(request.POST, request.FILES, instance=curso)
        if form.is_valid():
            form.save()
            return redirect('editar_cursos')
    else:
        form = CursoForm(instance=curso)

    return render(request, 'usuarios/editar_curso_individual.html', {
        'form': form,
        'curso': curso,
    })

@login_required
def eliminar_curso(request, id):
    # Obtener el curso con el ID proporcionado
    curso = get_object_or_404(Curso, id=id)

    # Verificar si el usuario es un administrador
    if not request.user.is_staff:  # Si no es administrador, redirige
        return redirect('gestionar_cursos')

    if request.method == "POST":
        # Eliminar el curso directamente (sin verificar relación docente)
        curso.delete()
        return redirect('gestionar_cursos')  # Redirigir a la página de gestión de cursos

    # Si alguien intenta acceder con GET, mostrar la confirmación de eliminación
    return render(request, 'usuarios/eliminar_curso.html', {'curso': curso})

@login_required
def libreria_recursos(request):
    if request.method == 'POST':
        form = RecursoForm(request.POST, request.FILES)
        if form.is_valid():
            recurso = form.save(commit=False)  # 👈 No guardar aún
            recurso.docente = request.user     # 👈 Asigna el docente actual
            recurso.save()                     # 👈 Ahora sí guarda
            return redirect('libreria_recursos')
    else:
        form = RecursoForm()
    
    recursos = Recurso.objects.filter(docente=request.user)  # 👈 Mostrar solo los recursos del docente
    return render(request, 'usuarios/libreria_recursos.html', {
        'form': form,
        'recursos': recursos
    })

@login_required
def editar_recurso(request, recurso_id):
    recurso = get_object_or_404(Recurso, id=recurso_id)

    if recurso.docente != request.user:
        return HttpResponseForbidden("No tienes permiso para editar este recurso.")

    if request.method == "POST":
        form = RecursoForm(request.POST, request.FILES, instance=recurso)
        if form.is_valid():
            form.save()
            return redirect('libreria_recursos')
    else:
        form = RecursoForm(instance=recurso)

    return render(request, 'usuarios/editar_recurso.html', {'form': form, 'recurso': recurso})

@login_required
def eliminar_recurso(request, recurso_id):
    recurso = get_object_or_404(Recurso, id=recurso_id)

    if recurso.docente != request.user:
        return HttpResponseForbidden("No tienes permiso para eliminar este recurso.")

    archivo_path = recurso.archivo.path if recurso.archivo else None

    recurso.delete()

    if archivo_path and os.path.exists(archivo_path):
        os.remove(archivo_path)

    return redirect('libreria_recursos')

@login_required
def detalle_recurso(request, recurso_id):
    recurso = get_object_or_404(Recurso, id=recurso_id)

    if recurso.docente != request.user:
        return HttpResponseForbidden("No tienes permiso para ver este recurso.")

    archivo_nombre = recurso.archivo.name.split('/')[-1]
    return render(request, 'usuarios/detalle_recurso.html', {'recurso': recurso, 'archivo_nombre': archivo_nombre})

from .forms import EditarPerfilDocenteForm, ImagenPerfilForm

def perfil_docente(request):
    user = request.user
    perfil = Perfil.objects.get(usuario=user)

    if request.method == 'POST':
        form = EditarPerfilDocenteForm(request.POST, instance=user)
        imagen_form = ImagenPerfilForm(request.POST, request.FILES, instance=perfil)

        # Guardamos copia del path anterior de la imagen
        imagen_anterior = perfil.imagen.path if perfil.imagen else None

        if form.is_valid() and imagen_form.is_valid():
            form.save()

            # Si el campo de imagen está vacío (se presionó "Clear") y antes tenía imagen
            if not request.FILES.get('imagen') and 'imagen-clear' in request.POST:
                if imagen_anterior and os.path.isfile(imagen_anterior):
                    os.remove(imagen_anterior)  # Borrar imagen del sistema
                perfil.imagen = None  # Borrar referencia en BD

            imagen_form.save()

            return redirect('perfil_docente')

    else:
        form = EditarPerfilDocenteForm(instance=user)
        imagen_form = ImagenPerfilForm(instance=perfil)

    return render(request, 'usuarios/perfil_docente.html', {
        'form': form,
        'imagen_form': imagen_form,
        'perfil': perfil,
    })
    
@login_required
def pagar_curso(request, inscripcion_id):
    inscripcion = get_object_or_404(CursoInscrito, id=inscripcion_id, estudiante=request.user)

    if request.method == 'POST':
        metodo_pago = request.POST.get('metodo_pago')
        numero_pago = request.POST.get('numero_pago')  # Si no usas este, puedes ignorarlo
        numero_transaccion = request.POST.get('numero_transaccion')

        inscripcion.pagado = True
        inscripcion.metodo_pago = metodo_pago
        inscripcion.numero_transaccion = numero_transaccion
        inscripcion.save()

        # Notificación al estudiante
        Notificacion.objects.create(
            titulo="Pago confirmado",
            contenido=f"Has pagado el curso '{inscripcion.curso_docente.curso.nombre}'.",
            tipo='mensaje',
            usuario=request.user,
            usuario_afectado=request.user
        )

        # Enviar factura
        enviar_factura_email(
            usuario=request.user,
            asunto='Factura de pago',
            template_html='usuarios/factura.html',
            context={
                'usuario': request.user,
                'varios': False,
                'curso': inscripcion.curso_docente.curso.nombre,
                'docente': inscripcion.curso_docente.docente.get_full_name() or inscripcion.curso_docente.docente.username,
                'monto': inscripcion.curso_docente.curso.costo,
            }
        )

        messages.success(request, "El curso ha sido pagado exitosamente.")
        return redirect('academica')

    return render(request, 'usuarios/pagar_curso.html', {
        'inscripcion': inscripcion,
        'monto': inscripcion.curso_docente.curso.costo,
        'varios': False,
    })


@login_required
def pagar_todos_los_cursos(request):
    cursos_no_pagados = CursoInscrito.objects.filter(estudiante=request.user, pagado=False)

    if request.method == 'POST':
        total = 0
        cantidad = cursos_no_pagados.count()

        for curso in cursos_no_pagados:
            curso.pagado = True
            curso.save()
            total += curso.curso_docente.curso.costo

        # Notificación al estudiante
        Notificacion.objects.create(
            titulo="Pago de cursos completado",
            contenido=f"Has pagado {cantidad} curso(s) por un total de ${total}.",
            tipo='mensaje',
            usuario=request.user,
            usuario_afectado=request.user
        )

        # Enviar factura
        enviar_factura_email(
            usuario=request.user,
            asunto='Factura de pago',
            template_html='usuarios/factura.html',
            context={
                'usuario': request.user,
                'varios': True,
                'cantidad': cantidad,
                'total': total
            }
        )

        messages.success(request, "Todos los cursos han sido pagados.")
        return redirect('academica')

    total = sum(curso.curso_docente.curso.costo for curso in cursos_no_pagados)

    return render(request, 'usuarios/pagar_curso.html', {
        'varios': True,
        'total': total,
        'cantidad': cursos_no_pagados.count(),
    })
    
from django.template.loader import render_to_string
    
def enviar_factura_email(usuario, asunto, template_html, context):
    contenido_html = render_to_string(template_html, context)

    send_mail(
        subject=asunto,
        message='',  # texto plano opcional
        from_email=None,
        recipient_list=[usuario.email],
        html_message=contenido_html
    )

@login_required
def cursos_pagados(request):
    cursos_pagados = CursoInscrito.objects.filter(
        estudiante=request.user, 
        pagado=True,
        curso_docente__isnull=False  # Aquí evitas los que no tienen curso_docente
    ).select_related('curso_docente__curso', 'curso_docente__docente')
    
    context = {
        'cursos_pagados': cursos_pagados
    }
    return render(request, 'usuarios/cursos_pagados.html', context)


@login_required
def ver_contenido_curso(request, curso_docente_id):
    try:
        inscripcion = CursoInscrito.objects.select_related('curso_docente__curso').get(
            curso_docente_id=curso_docente_id,
            estudiante=request.user,
            pagado=True
        )
    except CursoInscrito.DoesNotExist:
        return redirect('cursos_pagados')

    curso = inscripcion.curso_docente.curso
    unidades = curso.unidades.prefetch_related('sesiones').all()

    sesiones_completadas_ids = SesionCompletada.objects.filter(
        estudiante=request.user,
        sesion__unidad__curso=curso
    ).values_list('sesion_id', flat=True)

    context = {
        'curso': curso,
        'unidades': unidades,
        'sesiones_completadas_ids': sesiones_completadas_ids,
    }
    return render(request, 'usuarios/contenido_curso.html', context)

@login_required
def marcar_sesion_completada(request, sesion_id):
    sesion = get_object_or_404(Sesion, id=sesion_id)
    curso = sesion.unidad.curso
    estudiante = request.user

    # Buscar el curso_docente en el que el estudiante está inscrito y ha pagado
    curso_inscrito = CursoInscrito.objects.filter(
        estudiante=estudiante,
        curso_docente__curso=curso,
        pagado=True
    ).first()

    if not curso_inscrito:
        return redirect('panel_estudiante')  # o muestra un mensaje de error

    # Registrar la sesión como completada (si no lo está ya)
    SesionCompletada.objects.get_or_create(
        estudiante=estudiante,
        sesion=sesion
    )

    return redirect('ver_contenido_curso', curso_docente_id=curso_inscrito.curso_docente.id)

@login_required
def gestionar_unidades(request, curso_id):
    curso_docente = get_object_or_404(CursoDocente, curso_id=curso_id, docente=request.user)
    unidades = Unidad.objects.filter(curso=curso_docente.curso).order_by('orden')
    return render(request, 'usuarios/gestionar_unidades.html', {
        'curso': curso_docente.curso,
        'unidades': unidades,
    })

@login_required
def agregar_unidad(request, curso_id):
    curso_docente = get_object_or_404(CursoDocente, curso_id=curso_id, docente=request.user)

    if request.method == 'POST':
        form = UnidadForm(request.POST)
        if form.is_valid():
            unidad = form.save(commit=False)
            unidad.curso = curso_docente.curso
            unidad.save()
            return redirect('gestionar_unidades', curso_id=curso_id)
    else:
        form = UnidadForm()

    return render(request, 'usuarios/agregar_unidad.html', {
        'form': form,
        'curso': curso_docente.curso,
    })
    
@login_required
def agregar_sesion(request, unidad_id):
    unidad = get_object_or_404(Unidad, id=unidad_id, curso__cursodocente__docente=request.user)

    if request.method == 'POST':
        form = SesionForm(request.POST, request.FILES)
        if form.is_valid():
            sesion = form.save(commit=False)
            sesion.unidad = unidad
            sesion.save()
            return redirect('gestionar_unidades', curso_id=unidad.curso.id)
    else:
        form = SesionForm()

    return render(request, 'usuarios/agregar_sesion.html', {
        'form': form,
        'unidad': unidad,
    })

def eliminar_unidad(request, unidad_id):
    unidad = get_object_or_404(Unidad, id=unidad_id)
    curso_id = unidad.curso.id  # o como guardes la relación
    unidad.delete()
    messages.success(request, "Unidad eliminada correctamente.")
    return redirect('gestionar_unidades', curso_id=curso_id)

def eliminar_sesion(request, sesion_id):
    sesion = get_object_or_404(Sesion, id=sesion_id)
    curso_id = sesion.unidad.curso.id  # si la relación es Unidad -> Curso
    sesion.delete()
    messages.success(request, "Sesión eliminada correctamente.")
    return redirect('gestionar_unidades', curso_id=curso_id)

@login_required
def calificar_curso(request, curso_docente_id):
    inscripcion = get_object_or_404(
        CursoInscrito,
        curso_docente_id=curso_docente_id,
        estudiante=request.user,
        pagado=True
    )
    curso_docente = inscripcion.curso_docente
    curso = curso_docente.curso

    try:
        calificacion = CalificacionCurso.objects.get(curso=curso, estudiante=request.user)
    except CalificacionCurso.DoesNotExist:
        calificacion = None

    if request.method == 'POST':
        form = CalificacionForm(request.POST, instance=calificacion)
        if form.is_valid():
            nueva_calificacion = form.save(commit=False)
            nueva_calificacion.curso = curso
            nueva_calificacion.estudiante = request.user
            nueva_calificacion.save()

            # Actualizar promedio
            promedio = CalificacionCurso.objects.filter(curso=curso).aggregate(Avg('puntuacion'))['puntuacion__avg'] or 0
            curso.calificacion = round(promedio, 1)
            curso.save()

            # Crear notificación para el docente
            Notificacion.objects.create(
                titulo="Nueva calificación de curso",
                contenido=f"{request.user.username} ha calificado tu curso '{curso.nombre}' con {nueva_calificacion.puntuacion} estrellas.",
                tipo='mensaje',
                usuario=request.user,
                usuario_afectado=curso_docente.docente
            )

            return redirect('ver_contenido_curso', curso_docente_id)
    else:
        form = CalificacionForm(instance=calificacion)

    return render(request, 'usuarios/calificar_curso.html', {
        'form': form,
        'curso': curso,
        'curso_docente_id': curso_docente_id,
    })

def notificaciones(request):
    lista = Notificacion.objects.filter(
        eliminada=False,
        titulo__icontains='registro'  # busca las que tengan "registro" en el título
    ).order_by('-fecha')
    
    paginator = Paginator(lista, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    restaurado = request.GET.get('restaurado')
    
    return render(request, 'usuarios/notificaciones.html', {
        'notificaciones': page_obj,
        'restaurado': restaurado
    })

@login_required
def eliminar_notificacion(request, id):
    notificacion = get_object_or_404(Notificacion, id=id, usuario_afectado=request.user)
    notificacion.delete()
    return redirect('notificaciones')

@login_required
def marcar_notificacion_leida(request, id):
    notificacion = get_object_or_404(Notificacion, id=id, usuario_afectado=request.user)
    notificacion.visto = True
    notificacion.save()
    return redirect('notificaciones')

@login_required
def notificaciones_docente(request):
    # Obtener las notificaciones que no estén eliminadas y para el usuario
    notificaciones = Notificacion.objects.filter(
        usuario_afectado=request.user,
        eliminada=False
    ).exclude(titulo="Nuevo registro de usuario").order_by('-fecha')

    # Contar las no vistas (para mostrar el punto rojo)
    notificaciones_no_vistas = notificaciones.filter(visto=False).count()

    return render(request, 'usuarios/notificaciones_docente.html', {
        'notificaciones': notificaciones,
        'notificaciones_no_vistas': notificaciones_no_vistas,
    })
    
@login_required
def eliminar_notificacion_docente(request, id):
    notificacion = get_object_or_404(Notificacion, id=id, usuario_afectado=request.user)
    notificacion.delete()
    return redirect('notificaciones_docente')

@login_required
def marcar_notificacion_leida_docente(request, id):
    notificacion = get_object_or_404(Notificacion, id=id, usuario_afectado=request.user)
    notificacion.visto = True
    notificacion.save()
    return redirect('notificaciones_docente')

@login_required
def notificaciones_estudiante(request):
    notificaciones = Notificacion.objects.filter(
        usuario_afectado=request.user
    ).exclude(titulo="Nuevo registro de usuario").order_by('-fecha')

    return render(request, 'usuarios/notificaciones_estudiante.html', {
        'notificaciones': notificaciones
    })

@login_required
def eliminar_notificacion_estudiante(request, id):
    notificacion = get_object_or_404(Notificacion, id=id, usuario_afectado=request.user)
    notificacion.delete()
    return redirect('notificaciones_estudiante')

@login_required
def marcar_notificacion_leida_estudiante(request, id):
    notificacion = get_object_or_404(Notificacion, id=id, usuario_afectado=request.user)
    notificacion.visto = True
    notificacion.save()
    return redirect('notificaciones_estudiante')

@login_required
def eliminar_curso_pagado(request, inscripcion_id):
    inscripcion = get_object_or_404(CursoInscrito, id=inscripcion_id, estudiante=request.user)

    if request.method == 'POST':
        curso_nombre = inscripcion.curso_docente.curso.nombre  # Guardar nombre antes de eliminar
        inscripcion.delete()

        # Crear notificación al estudiante
        Notificacion.objects.create(
            titulo="Curso eliminado",
            contenido=f"Has eliminado el curso '{curso_nombre}'. Si deseas acceder nuevamente, deberás volver a inscribirte y pagarlo.",
            tipo='advertencia',
            usuario=request.user,
            usuario_afectado=request.user
        )

        messages.success(request, 'El curso ha sido eliminado. Si deseas acceder nuevamente, deberás volver a inscribirte y pagarlo.')
        return redirect('cursos_pagados')

    messages.error(request, 'Ocurrió un error al intentar eliminar el curso.')
    return redirect('cursos_pagados')

@login_required
def progreso(request):
    cursos_inscritos = CursoInscrito.objects.filter(estudiante=request.user, pagado=True)

    progreso_cursos = []
    for inscripcion in cursos_inscritos:
        curso = inscripcion.curso_docente.curso

        total_sesiones = 0
        sesiones_completadas = 0
        total_unidades = curso.unidades.count()
        unidades_completadas = 0

        for unidad in curso.unidades.all():
            sesiones_unidad = unidad.sesiones.all()
            total_sesiones_unidad = sesiones_unidad.count()
            total_sesiones += total_sesiones_unidad

            completadas_unidad = 0
            for sesion in sesiones_unidad:
                if SesionCompletada.objects.filter(estudiante=request.user, sesion=sesion).exists():
                    completadas_unidad += 1
            sesiones_completadas += completadas_unidad

            if total_sesiones_unidad > 0 and completadas_unidad == total_sesiones_unidad:
                unidades_completadas += 1

        progreso_sesiones = int((sesiones_completadas / total_sesiones) * 100) if total_sesiones > 0 else 0
        progreso_unidades = int((unidades_completadas / total_unidades) * 100) if total_unidades > 0 else 0
        progreso_total = progreso_sesiones  # Solo basado en sesiones

        progreso_cursos.append({
            'curso': curso,
            'progreso_sesiones': progreso_sesiones,
            'total_sesiones': total_sesiones,
            'completadas_sesiones': sesiones_completadas,
            'progreso_unidades': progreso_unidades,
            'total_unidades': total_unidades,
            'completadas_unidades': unidades_completadas,
            'progreso_total': progreso_total,
        })

    return render(request, 'usuarios/progreso.html', {'progreso_cursos': progreso_cursos})

@login_required
def progreso_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)

    unidades_info = []
    for unidad in curso.unidades.all().order_by('orden'):
        sesiones = unidad.sesiones.all().order_by('orden')
        sesiones_info = []
        completadas = 0

        for sesion in sesiones:
            completada = SesionCompletada.objects.filter(
                estudiante=request.user,
                sesion=sesion
            ).exists()
            if completada:
                completadas += 1
            sesiones_info.append({
                'sesion': sesion,
                'completada': completada,
            })

        total = sesiones.count()
        porcentaje = int((completadas / total) * 100) if total > 0 else 0

        unidades_info.append({
            'unidad': unidad,
            'sesiones': sesiones_info,
            'completadas': completadas,
            'total': total,
            'porcentaje': porcentaje,
        })

    context = {
        'curso': curso,
        'unidades_info': unidades_info,
    }
    return render(request, 'usuarios/progreso_curso.html', context)

@login_required
def ver_certificado(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)

    # Generamos número único de certificado
    numero_certificado = f'KABLI-{request.user.id}-{curso.id}'

    # URL de verificación del certificado (ajústala según tu dominio real)
    url_verificacion = f'https://kabli.com/verificar/{numero_certificado}'

    contexto = {
        'curso': curso,
        'fecha_finalizacion': date.today(),
        'numero_certificado': numero_certificado,
        'url_verificacion': url_verificacion,
        'user': request.user
    }

    return render(request, 'usuarios/certificado.html', contexto)

@login_required
def certificados_cursos(request):
    cursos_inscritos = CursoInscrito.objects.filter(estudiante=request.user, pagado=True)
    certificados = []

    for inscripcion in cursos_inscritos:
        curso = inscripcion.curso_docente.curso

        total_sesiones = 0
        sesiones_completadas = 0

        for unidad in curso.unidades.all():
            sesiones_unidad = unidad.sesiones.all()
            total_sesiones += sesiones_unidad.count()

            for sesion in sesiones_unidad:
                if SesionCompletada.objects.filter(estudiante=request.user, sesion=sesion).exists():
                    sesiones_completadas += 1

        progreso = int((sesiones_completadas / total_sesiones) * 100) if total_sesiones > 0 else 0

        if progreso == 100:
            numero_certificado = f'KABLI-{request.user.id}-{curso.id}'
            url_verificacion = f'https://kabli.com/verificar/{numero_certificado}'

            certificados.append({
                'curso': curso,
                'fecha_finalizacion': date.today(),  # opcional: puedes guardar la fecha real
                'numero_certificado': numero_certificado,
                'url_verificacion': url_verificacion,
            })

    return render(request, 'usuarios/certificados_cursos.html', {
        'certificados': certificados,
        'user': request.user,
    })

def ver_factura_curso(request, inscripcion_id):
    cursoinscrito = get_object_or_404(CursoInscrito, id=inscripcion_id, estudiante=request.user)

    if not cursoinscrito.pagado:
        return redirect('panel_estudiantes')

    return render(request, 'usuarios/factura_curso.html', {'inscripcion': cursoinscrito})

