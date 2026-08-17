"""URLs raiz do projeto EBD."""
from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import include, path

from ebd.core.forms import LoginForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'accounts/login/',
        LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=LoginForm,
        ),
        name='login',
    ),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('ebd.core.urls')),
]
