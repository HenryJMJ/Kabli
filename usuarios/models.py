from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.models import User
import string
import random
from datetime import timedelta
from django.db.models import Avg

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
    imagen = models.ImageField(upload_to='perfiles/', blank=True, null=True)
    categoria = models.ForeignKey('categoria', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.get_rol_display()}"
    

class PerfilEstudiante(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    identificacion = models.CharField(max_length=20, blank=True)
    edad = models.IntegerField(null=True, blank=True)
    telefono = models.CharField(max_length=15, blank=True)
    departamento = models.CharField(max_length=50, blank=True)
    ciudad = models.CharField(max_length=50, blank=True)
    foto_perfil = models.ImageField(upload_to='fotos_perfil/', blank=True, null=True)

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

    # ✅ Campo nuevo
    visto = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.titulo} - {self.get_tipo_display()}"

    
class Curso(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    activo = models.BooleanField(default=True)
    total_unidades = models.PositiveIntegerField(default=3)
    unidades_completadas = models.PositiveIntegerField(default=0)
    imagen = models.ImageField(upload_to='cursos/', null=True, blank=True)
    total_sesiones = models.PositiveIntegerField(default=20)
    costo = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    calificacion = models.FloatField(default=0.0)
    categoria = models.ForeignKey('Categoria', on_delete=models.SET_NULL, null=True, blank=True, related_name='cursos')

    def __str__(self):
        return self.nombre

    def esta_deshabilitado(self):
        return self.unidades_completadas >= self.total_unidades
    
    def promedio_calificaciones(self):
        promedio = self.calificacioncurso_set.aggregate(prom=Avg('puntuacion'))['prom']
        return promedio if promedio is not None else 0.0

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
    pagado = models.BooleanField(default=False)  # Nuevo campo
    numero_transaccion = models.CharField(max_length=100, blank=True, null=True)  # Ejemplo
    metodo_pago = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ('curso_docente', 'estudiante')

    def __str__(self):
        return f"{self.estudiante.username} inscrito en {self.curso_docente.curso.nombre}"
    
    def progreso_porcentaje(self):
        total_sesiones = Sesion.objects.filter(unidad__curso=self.curso_docente.curso).count()
        completadas = SesionCompletada.objects.filter(
            estudiante=self.estudiante,
            sesion__unidad__curso=self.curso_docente.curso
        ).count()

        if total_sesiones == 0:
            return 0
        return int((completadas / total_sesiones) * 100)

class Unidad(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='unidades')
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.curso.nombre} - Unidad {self.orden}: {self.titulo}"

class Sesion(models.Model):
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, related_name='sesiones')
    titulo = models.CharField(max_length=200)
    contenido_texto = models.TextField(blank=True)
    video_url = models.URLField(blank=True, null=True)  # si hay videos externos
    archivo = models.FileField(upload_to='cursos/materiales/', blank=True, null=True)
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.unidad} - Sesión {self.orden}: {self.titulo}"
    
class SesionCompletada(models.Model):
    sesion = models.ForeignKey(Sesion, on_delete=models.CASCADE)
    estudiante = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_completado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sesion', 'estudiante')

    def __str__(self):
        return f"{self.estudiante.username} completó {self.sesion}"
    
class CalificacionCurso(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    estudiante = models.ForeignKey(User, on_delete=models.CASCADE)
    puntuacion = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])  # 1 a 5
    comentario = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('curso', 'estudiante')  # Cada estudiante califica un curso una vez

    def __str__(self):
        return f"{self.estudiante.username} calificó {self.curso.nombre} con {self.puntuacion}"
    
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre
    
class Recurso(models.Model):
    nombre = models.CharField(max_length=100, default="Recurso sin nombre")
    archivo = models.FileField(upload_to='recursos/')
    descripcion = models.TextField(blank=True, null=True)
    fecha_agregado = models.DateTimeField(auto_now_add=True)
    docente = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.nombre

