from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "Suzuki Tec - Administração"
admin.site.site_title = "Suzuki Tec"
admin.site.index_title = "Painel de Controle"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.clients.urls")),
    path("relatorios/", include("apps.reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
