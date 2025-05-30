from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Perfil
from .models import PerfilEstudiante
from .models import Curso
from .models import Recurso
from .models import Unidad, Sesion, CalificacionCurso


class RegistroForm(UserCreationForm):
    email = forms.EmailField(
        label="Correo Electrónico",
        required=True,
        error_messages={'required': 'Por favor, ingresa un correo válido'}
    )

    rol = forms.ChoiceField(
        choices=Perfil.ROLES,
        label="Rol",
        required=True,
        error_messages={'required': 'Selecciona un rol'}
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            Perfil.objects.create(usuario=user, rol=self.cleaned_data['rol'])
        return user

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        labels = {
            'username': 'Nombre de Usuario',
            'email': 'Correo Electrónico',
            'password1': 'Contraseña',
            'password2': 'Confirmar Contraseña',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso.")
        return username
    
class CursoForm(forms.ModelForm):
    imagen = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
        })
    )

    class Meta:
        model = Curso
        fields = ['nombre', 'descripcion', 'imagen', 'categoria']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del curso'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción del curso'
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-control',
            }),
        }

class RecursoForm(forms.ModelForm):
    class Meta:
        model = Recurso
        fields = ['nombre', 'descripcion', 'archivo']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].initial = 'Nombre del recurso'
        
class PerfilEstudianteForm(forms.ModelForm):
    class Meta:
        model = PerfilEstudiante
        fields = ['identificacion', 'edad', 'telefono', 'departamento', 'ciudad']

    def clean_edad(self):
        edad = self.cleaned_data.get('edad')
        if edad == '':
            return None  # Si el campo está vacío, devolver None (o el valor predeterminado adecuado)
        return edad
    
class MensajeForm(forms.Form):
    asunto = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Asunto'}))
    mensaje = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'Escribe tu mensaje aquí...'}))
    
class EditarPerfilDocenteForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        
class UnidadForm(forms.ModelForm):
    class Meta:
        model = Unidad
        fields = ['titulo', 'descripcion', 'orden']
        
class SesionForm(forms.ModelForm):
    class Meta:
        model = Sesion
        fields = ['titulo', 'contenido_texto', 'video_url', 'archivo', 'orden']
        
class CalificacionForm(forms.ModelForm):
    class Meta:
        model = CalificacionCurso
        fields = ['puntuacion', 'comentario']
        widgets = {
            'puntuacion': forms.RadioSelect(choices=[(i, f"{i} ⭐") for i in range(1,6)]),
            'comentario': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tu opinión...'}),
        }
        
class ImagenPerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['imagen']