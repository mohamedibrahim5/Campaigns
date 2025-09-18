"""
URL configuration for tg_hub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from hub import views as hub_views
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('hub/', include('hub.urls')),
    path('admin/', admin.site.urls),
    path('login/', hub_views.candidate_login_simple, name='candidate_login_root'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('accounts/profile/', RedirectView.as_view(url='/hub/election-dashboard/', permanent=False), name='profile'),
    # Catch-all pretty candidate name at root. Keep LAST to avoid shadowing.
    path('<path:candidate_name>/', hub_views.candidate_landing_by_name, name='candidate_landing_by_name'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
