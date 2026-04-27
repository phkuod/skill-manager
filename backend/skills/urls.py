from django.conf import settings
from django.urls import path, re_path
from django.views.static import serve as static_serve

from . import views

urlpatterns = [
    # HTML shells. Useful for local dev (./start.sh); in a split deployment
    # the frontend is served from a static host and these are unused.
    path('', views.index_shell, name='home'),
    path('index.html', views.index_shell),
    path('skill.html', views.skill_shell, name='skill_detail'),

    # Frontend static assets at root URLs so HTML files can use relative
    # paths (vendor/x.css, assets/x.js, config.js). Same URLs work whether
    # served by Django or by a plain static host.
    re_path(
        r'^(?P<path>(?:vendor|assets)/.+|config\.js)$',
        static_serve,
        {'document_root': settings.FRONTEND_DIR},
    ),

    # JSON API
    path('api/health', views.api_health, name='api_health'),
    path('api/skills', views.api_skill_list, name='api_skill_list'),
    path('api/skills/<str:name>', views.api_skill_detail, name='api_skill_detail'),
    path('api/skills/<str:name>/zip', views.api_skill_zip, name='api_skill_zip'),
    path('api/skills/<str:name>/files', views.api_skill_files, name='api_skill_files'),
    path('api/skills/<str:name>/versions', views.api_versions, name='api_versions'),
    path('api/skills/<str:name>/versions/<str:version>', views.api_version_detail, name='api_version_detail'),
    path('api/skills/<str:name>/versions/<str:version>/zip', views.api_version_zip, name='api_version_zip'),
    path('api/skills/<str:name>/versions/<str:version>/files', views.api_version_files, name='api_version_files'),
]
