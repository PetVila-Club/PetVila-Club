from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

admin.site.site_header = "PetVila Club · Painel"
admin.site.site_title = "PetVila Club"
admin.site.index_title = "Operação da Vila"

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/v1/", include("config.api_urls")),
    path("painel/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
