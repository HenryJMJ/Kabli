from django.shortcuts import render, redirect, get_object_or_404
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
from .models import Notificacion
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from .models import Curso
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
def panel_docentes(request):
    try:
        if request.user.perfil.rol != 'docente':
            return redirect('login')  # O podrías usar un error 403
    except Perfil.DoesNotExist:
        return redirect('login')

    return render(request, 'usuarios/panel_docentes.html', {
        'username': request.user.username
    })

def libreria_cursos(request):
    cursos = Curso.objects.all()
    return render(request, 'usuarios/libreria_cursos.html', {'cursos': cursos})

# Vista para la lista de estudiantes inscritos en el curso
def estudiantes_curso(request):
    return render(request, 'usuarios/estudiantes_curso.html')

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
    cursos = Curso.objects.filter(docente=request.user)
    return render(request, 'usuarios/cursos.html', {'cursos': cursos})

@login_required
def crear_curso(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        Curso.objects.create(nombre=nombre, descripcion=descripcion, docente=request.user)
        return redirect('gestionar_cursos')  # Asegúrate que esta URL exista
    return render(request, 'usuarios/crear_curso.html')

@login_required
def editar_cursos(request):
    cursos = Curso.objects.filter(docente=request.user)  # o todos los cursos si no querés filtrarlos
    return render(request, 'usuarios/editar_cursos.html', {'cursos': cursos})

@login_required
def editar_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id, docente=request.user)

    if request.method == 'POST':
        form = CursoForm(request.POST, instance=curso)
        if form.is_valid():
            form.save()
            return redirect('editar_cursos')  # Vuelve al listado
    else:
        form = CursoForm(instance=curso)

    return render(request, 'usuarios/editar_curso_individual.html', {'form': form, 'curso': curso})

@login_required
def eliminar_curso(request, id):
    curso = get_object_or_404(Curso, id=id, docente=request.user)
    
    if request.method == "POST":
        curso.delete()
        return redirect('editar_cursos')  # o 'editar_cursos' si ese es el nombre correcto

    # Si alguien intenta acceder con GET, lo redirigimos
    return redirect('gestionar_cursos')

@login_required
def libreria_recursos(request):
    if request.method == 'POST':
        form = RecursoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('libreria_recursos')
    else:
        form = RecursoForm()
    
    recursos = Recurso.objects.all()
    return render(request, 'usuarios/libreria_recursos.html', {
        'form': form,
        'recursos': recursos
    })

@login_required
def editar_recurso(request, recurso_id):
    recurso = get_object_or_404(Recurso, id=recurso_id)

    if request.method == "POST":
        form = RecursoForm(request.POST, request.FILES, instance=recurso)
        if form.is_valid():
            form.save()
            return redirect('libreria_recursos')  # Redirigir a la página de recursos
    else:
        form = RecursoForm(instance=recurso)

    return render(request, 'usuarios/editar_recurso.html', {'form': form, 'recurso': recurso})

@login_required
def eliminar_recurso(request, recurso_id):
    # Obtener el recurso
    recurso = get_object_or_404(Recurso, id=recurso_id)

    # Obtener la ruta del archivo en el sistema de archivos
    archivo_path = recurso.archivo.path if recurso.archivo else None

    # Eliminar el recurso de la base de datos
    recurso.delete()

    # Eliminar el archivo del sistema si existe
    if archivo_path and os.path.exists(archivo_path):
        os.remove(archivo_path)

    # Redirigir a la página de recursos después de la eliminación
    return redirect('libreria_recursos')