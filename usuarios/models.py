from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.models import User
import string
import random
from datetime import timedelta

User = get_user_model()

def generate_code():
    return ''.join(random.choices(string.digits, k=6))


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6, unique=True)  # Código de 6 dígitos
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = str(random.randint(100000, 999999))
        super().save(*args, **kwargs)

    def is_valid(self):
        tiempo_expiracion = timedelta(minutes=10)
        return not self.is_used and timezone.now() - self.created_at <= tiempo_expiracion

    def __str__(self):
        return f"{self.user.username} - {self.code}"

class Perfil(models.Model):
    ROLES = (
        ('docente', 'Docente'),
        ('estudiante', 'Estudiante'),
    )
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    rol = models.CharField(max_length=20, choices=ROLES, default='estudiante')
    verificado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.usuario.username} - {self.get_rol_display()}"
    

class PerfilEstudiante(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    identificacion = models.CharField(max_length=20, blank=True)
    edad = models.IntegerField(null=True, blank=True)
    telefono = models.CharField(max_length=15, blank=True)
    departamento = models.CharField(max_length=50, blank=True)
    ciudad = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Perfil de {self.usuario.username}"
    
class Acceso(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('info', 'Información'),
        ('advertencia', 'Advertencia'),
        ('mensaje', 'Mensaje'),
    ]

    titulo = models.CharField(max_length=100)
    contenido = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='info')
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notificaciones_creadas')
    usuario_afectado = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notificaciones_recibidas')
    eliminada = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.titulo} - {self.get_tipo_display()}"
    
class Curso(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    activo = models.BooleanField(default=True)
    total_unidades = models.PositiveIntegerField(default=3)  # Número de unidades de curso
    unidades_completadas = models.PositiveIntegerField(default=0)  # Unidades completadas por docentes
    imagen = models.ImageField(upload_to='cursos/', null=True, blank=True)  # Campo de imagen
    total_sesiones = models.PositiveIntegerField(default=20)  # Sesiones de clase, por defecto 20

    def __str__(self):
        return self.nombre

    def esta_deshabilitado(self):
        # El curso se deshabilita cuando se completan todas las unidades
        return self.unidades_completadas >= self.total_unidades

class CursoDocente(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    docente = models.ForeignKey(User, on_delete=models.CASCADE)
    publicado = models.BooleanField(default=False)

    class Meta:
        unique_together = ('curso', 'docente')

    def save(self, *args, **kwargs):
        if not self.pk:
            curso = self.curso
            if curso.unidades_completadas < curso.total_unidades:
                curso.unidades_completadas += 1
                curso.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.docente.username} - {self.curso.nombre}"
 
class CursoInscrito(models.Model):
    curso_docente = models.ForeignKey(CursoDocente, on_delete=models.CASCADE)
    estudiante = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('curso_docente', 'estudiante')

    def __str__(self):
        return f"{self.estudiante.username} inscrito en {self.curso_docente.curso.nombre}"
 
    
class Recurso(models.Model):
    nombre = models.CharField(max_length=100, default="Recurso sin nombre")
    archivo = models.FileField(upload_to='recursos/')
    descripcion = models.TextField(blank=True, null=True)
    fecha_agregado = models.DateTimeField(auto_now_add=True)
    docente = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.nombre
