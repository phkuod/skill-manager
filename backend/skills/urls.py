from django.urls import path
from . import views

urlpatterns = [
    # HTML shells (static, no templating — the frontend JS fetches /api/*)
    path('', views.index_shell, name='home'),
    path('skill/<str:name>', views.skill_shell, name='skill_detail'),

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
