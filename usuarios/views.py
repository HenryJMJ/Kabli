from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
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
from django.db.models import Count
from django.db.models.functions import TruncDate
from collections import defaultdict
from .models import Notificacion
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from .models import Curso
from .models import CursoDocente
from .models import CursoInscrito
from .models import PerfilEstudiante
from .forms import CursoForm
from .models import Recurso
from .forms import RecursoForm


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
    return render(request, 'usuarios/panel_admin.html', {
        'usuarios': usuarios,
        'show_welcome': show_welcome
    })

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

# vista estadisticas:
def estadisticas(request):
    total_usuarios = User.objects.count()
    total_docentes = Perfil.objects.filter(rol='docente').count()
    total_estudiantes = Perfil.objects.filter(rol='estudiante').count()

    try:
        ultimo_usuario = User.objects.latest('date_joined')
        fecha_ultimo_registro = localtime(ultimo_usuario.date_joined).strftime('%d/%m/%Y')
    except User.DoesNotExist:
        fecha_ultimo_registro = "No hay usuarios"

    # Datos para gráfico de roles
    usuarios_por_rol = {
        'Administrador': User.objects.filter(is_superuser=True).count(),
        'Docente': total_docentes,
        'Estudiante': total_estudiantes,
    }

    roles_labels = json.dumps(list(usuarios_por_rol.keys()))
    roles_counts = json.dumps(list(usuarios_por_rol.values()))

    # Lista de registros de usuarios para el panel adicional
    registros = User.objects.all().order_by('-date_joined')
    registros_format = [
        {
            'nombre': f"{u.first_name} {u.last_name}".strip() or u.username,
            'correo': u.email,
            'fecha': localtime(u.date_joined)
        }
        for u in registros
    ]

    # 🆕 Cálculo del Pico de Actividad y Usuario Más Activo
    actividad_diaria = User.objects.annotate(fecha=TruncDate('date_joined')).values('fecha').annotate(total=Count('id')).order_by('-total')
    pico = actividad_diaria.first()
    pico_actividad = f"{pico['fecha'].strftime('%d/%m/%Y')} ({pico['total']} registros)" if pico else "Sin datos"

    usuario_top = User.objects.values('id', 'first_name', 'last_name', 'username').annotate(total=Count('date_joined')).order_by('-total').first()
    usuario_mas_activo = (
        f"{usuario_top['first_name']} {usuario_top['last_name']}".strip() or usuario_top['username']
    ) + f" ({usuario_top['total']} registros)" if usuario_top else "Sin datos"

    context = {
        'total_usuarios': total_usuarios,
        'total_docentes': total_docentes,
        'total_estudiantes': total_estudiantes,
        'fecha_ultimo_registro': fecha_ultimo_registro,
        'roles_labels': roles_labels,
        'roles_counts': roles_counts,
        'registros': registros_format,
        'pico_actividad': pico_actividad,
        'usuario_mas_activo': usuario_mas_activo,
    }

    return render(request, 'usuarios/estadisticas.html', context)

def gestion_academica(request):
    return render(request, 'usuarios/gestion_academica.html')

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

def notificaciones(request):
    lista = Notificacion.objects.filter(eliminada=False).order_by('-fecha')
    paginator = Paginator(lista, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    restaurado = request.GET.get('restaurado')
    return render(request, 'usuarios/notificaciones.html', {
        'notificaciones': page_obj,
        'restaurado': restaurado
    })

def eliminar_notificacion(request, id):
    if request.method == 'POST':
        notificacion = get_object_or_404(Notificacion, id=id)
        notificacion.eliminada = True
        notificacion.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@csrf_exempt  # Puedes quitarlo si ya estás usando CSRF desde JS
def restaurar_notificacion(request, id):
    if request.method == 'POST':
        notificacion = get_object_or_404(Notificacion, id=id)
        notificacion.eliminada = False
        notificacion.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

def registro(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()

                rol = form.cleaned_data['rol']
                grupo, _ = Group.objects.get_or_create(name=rol)
                user.groups.add(grupo)

                # ✅ Crear notificación
                Notificacion.objects.create(
                    titulo="Nuevo registro de usuario",
                    contenido=f"Se ha registrado a {user.first_name} {user.last_name} con el rol de {rol.capitalize()}.",
                    tipo='info',
                    usuario=request.user if request.user.is_authenticated else None,
                    usuario_afectado=user
                )

                messages.success(request, "Registro exitoso. Inicia sesión.")
                return redirect('login')

            except IntegrityError:
                messages.error(request, "Hubo un error al crear el usuario. Intenta de nuevo.")
                return redirect('registro')
        else:
            messages.error(request, "Corrige los errores a continuación.")
    else:
        form = RegistroForm()

    return render(request, 'usuarios/registro.html', {'form': form})

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
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if user.is_superuser or user.is_staff:
                return redirect('panel_admin')
            else:
                try:
                    perfil = user.perfil
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

    return render(request, 'usuarios/login.html')

@login_required
def panel_estudiantes(request):
    if request.user.perfil.rol != 'estudiante':
        return redirect('login')  # o redirige a su panel correspondiente

    nombre = request.user.first_name or request.user.username
    return render(request, 'usuarios/panel_estudiantes.html', {'nombre_usuario': nombre})

@login_required
def cursos_disponibles(request):
    # Filtra solo los cursos donde "publicado=True"
    cursos_publicados = CursoDocente.objects.filter(publicado=True)

    # Verificar si el estudiante está inscrito en cada curso
    cursos_con_estado = []
    for curso_docente in cursos_publicados:
        # Divide la descripción en palabras
        descripcion_palabras = curso_docente.curso.descripcion.split(' ')
        curso_docente.descripcion_palabras = descripcion_palabras
        
        # Verificar si el estudiante está inscrito en este curso
        esta_inscrito = CursoInscrito.objects.filter(estudiante=request.user, curso_docente=curso_docente).exists()
        
        # Añadir el estado de inscripción al curso
        cursos_con_estado.append({
            'curso': curso_docente,
            'inscrito': esta_inscrito
        })

    # Pasa la lista de cursos con su estado de inscripción al template
    return render(request, 'usuarios/cursos_disponibles.html', {
        'cursos_con_estado': cursos_con_estado
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
    # Obtén el curso docente y el curso correspondiente
    curso_docente = get_object_or_404(CursoDocente, id=id, publicado=True)
    curso = curso_docente.curso
    docente = curso_docente.docente

    # Verificar si el estudiante ya está inscrito en este curso
    estudiante = request.user  # Suponiendo que el estudiante está autenticado
    ya_inscrito = CursoInscrito.objects.filter(estudiante=estudiante, curso_docente=curso_docente).exists()

    return render(request, 'usuarios/detalle_curso.html', {
        'curso': curso,
        'docente': docente,
        'ya_inscrito': ya_inscrito,
    })

@login_required
def inscribir_curso(request, curso_docente_id):
    curso = get_object_or_404(CursoDocente, id=curso_docente_id)

    if request.method == 'POST':
        if CursoInscrito.objects.filter(curso_docente=curso, estudiante=request.user).exists():
            return render(request, 'usuarios/ya_inscrito.html')
        
        CursoInscrito.objects.create(curso_docente=curso, estudiante=request.user)
        
        # Agregar mensaje de inscripción exitosa
        messages.success(request, "¡Inscripción exitosa!")
        
        # Redirigir a la página de cursos disponibles
        return redirect('cursos_disponibles')  # Cambiar 'cursos_disponibles' por la vista adecuada

    return render(request, 'usuarios/inscribir_curso.html', {'curso': curso})

@login_required
def estudiantes_curso(request):
    # Obtener los cursos publicados por el docente logueado
    cursos_publicados = CursoDocente.objects.filter(docente=request.user, publicado=True)
    
    # Obtener las inscripciones a los cursos de ese docente
    inscripciones = CursoInscrito.objects.filter(curso_docente__in=cursos_publicados).select_related('estudiante', 'curso_docente__curso')

    # Organizar los estudiantes por curso
    cursos_con_estudiantes = defaultdict(list)

    for inscripcion in inscripciones:
        curso_nombre = inscripcion.curso_docente.curso.nombre
        estudiante_info = {
            'nombre': inscripcion.estudiante.get_full_name() or inscripcion.estudiante.username,
            'fecha': inscripcion.fecha_inscripcion.strftime('%d/%m/%Y %H:%M'),
        }
        cursos_con_estudiantes[curso_nombre].append(estudiante_info)

    return render(request, 'usuarios/estudiantes_curso.html', {'cursos_con_estudiantes': dict(cursos_con_estudiantes)})

@login_required
def perfil_estudiante(request):
    # Obtener o crear el perfil del estudiante
    perfil_estudiante, created = PerfilEstudiante.objects.get_or_create(usuario=request.user)

    if request.method == "POST":
        # Actualizar los datos del usuario (nombre y correo)
        request.user.first_name = request.POST.get('nombre', "")
        request.user.email = request.POST.get('correo', "")
        
        # Actualizar los campos del perfil
        perfil_estudiante.identificacion = request.POST.get('identificacion', "")
        edad = request.POST.get('edad', "")
        perfil_estudiante.edad = int(edad) if edad else None  # Asignar None si la edad está vacía
        perfil_estudiante.telefono = request.POST.get('telefono', "")
        perfil_estudiante.departamento = request.POST.get('departamento', "")
        perfil_estudiante.ciudad = request.POST.get('ciudad', "")

        # Guardar los cambios
        try:
            request.user.save()  # Guardar cambios del usuario
            perfil_estudiante.save()  # Guardar cambios del perfil

            # Mensaje de éxito
            messages.success(request, "¡Perfil actualizado correctamente!")
        except Exception as e:
            messages.error(request, f"Hubo un error al actualizar el perfil: {e}")
        
        # Redireccionar a la misma página para mostrar el perfil actualizado
        return redirect('perfil_estudiante')

    # Renderizar la página con el perfil actual
    return render(request, 'usuarios/perfil_estudiante.html', {
        'usuario': request.user,
        'perfil_estudiante': perfil_estudiante
    })

@login_required
def panel_docentes(request):
    try:
        if request.user.perfil.rol != 'docente':
            return redirect('login')  # O podrías usar un error 403
    except Perfil.DoesNotExist:
        return redirect('login')

    recursos = Recurso.objects.filter(docente=request.user)  # Filtra los recursos por el docente actual

    return render(request, 'usuarios/panel_docentes.html', {
        'username': request.user.username,
        'recursos': recursos  # Pasa los recursos filtrados a la plantilla
    })

@login_required
def libreria_cursos(request):
    cursos = Curso.objects.all()
    usuario = request.user

    # Obtener los cursos asignados al docente
    cursos_asignados = CursoDocente.objects.filter(docente=usuario)

    for curso in cursos:
        # Verificar si el docente ya tiene este curso asignado
        curso.agregado = CursoDocente.objects.filter(curso=curso, docente=usuario).exists()

        # Calcular cuántos docentes tienen asignado este curso
        curso.cursos_asignados = CursoDocente.objects.filter(curso=curso).count()

        curso.completado = curso.unidades_completadas >= curso.total_unidades

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

@login_required
def ver_estudiantes(request):
    return render(request, 'usuarios/estudiantes.html')

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
                f'Tu código de verificación es: {code_instance.code}',
                settings.DEFAULT_FROM_EMAIL,
                [email]
            )
            request.session['reset_user_id'] = user.id
            messages.success(request, 'Se ha enviado un código a tu correo.')
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
        
        # Crear el curso sin asignar docente
        curso = Curso.objects.create(nombre=nombre, descripcion=descripcion)
        
        # Si el admin quiere asignar docentes, lo hace aquí (se puede modificar según los requisitos)
        docentes = request.POST.getlist('docentes')  # 'docentes' es el campo que puede venir de un formulario o algo similar
        for docente_id in docentes:
            docente = User.objects.get(id=docente_id)
            CursoDocente.objects.create(curso=curso, docente=docente)

        return redirect('gestionar_cursos')  # Redirigir después de crear el curso
    
    return render(request, 'usuarios/crear_curso.html')

@login_required
def editar_cursos(request):
    cursos = Curso.objects.all()
    return render(request, 'usuarios/editar_cursos.html', {'cursos': cursos})

@login_required
def editar_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)  # Ya no filtramos por docente

    if request.method == 'POST':
        form = CursoForm(request.POST, instance=curso)
        if form.is_valid():
            form.save()
            return redirect('editar_cursos')  # Redirecciona al listado
    else:
        form = CursoForm(instance=curso)

    return render(request, 'usuarios/editar_curso_individual.html', {'form': form, 'curso': curso})

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