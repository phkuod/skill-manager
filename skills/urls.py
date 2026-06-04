from django.urls import path

from . import views, views_v1

urlpatterns = [
    path('', views.home, name='home'),
    path('skills/<str:name>/', views.skill_detail, name='skill_detail'),
    path('skills/<str:name>/v/<str:version>/', views.skill_detail_version, name='skill_detail_version'),
    path('installed/', views.installed_page, name='installed_page'),
    path('usage/', views.usage_page, name='usage_page'),

    # Skill contributions (phase 1: human-reviewed; phase 2 layers AI review)
    path('contribute/', views.contribute_page, name='contribute_page'),
    path('contributions/', views.my_contributions_page, name='my_contributions_page'),
    path('contributions/<int:submission_id>/',
         views.contribution_detail_page, name='contribution_detail_page'),
    path('admin/contributions/',
         views.admin_contributions_page, name='admin_contributions_page'),

    path('api/contribute/submit', views.api_contribute_submit, name='api_contribute_submit'),
    path('api/contributions/<int:submission_id>/zip',
         views.api_contribution_zip, name='api_contribution_zip'),
    path('api/contributions/<int:submission_id>/status',
         views.api_contribution_status, name='api_contribution_status'),
    path('api/contributions/<int:submission_id>/comment',
         views.api_contribution_comment, name='api_contribution_comment'),
    path('api/contributions/<int:submission_id>/publish',
         views.api_contribution_publish, name='api_contribution_publish'),
    path('api/contributions/<int:submission_id>/delete',
         views.api_contribution_delete, name='api_contribution_delete'),

    # Usage dashboard JSON (admin-gated)
    path('api/usage/summary', views.api_usage_summary, name='api_usage_summary'),
    path('api/usage/installs', views.api_usage_installs, name='api_usage_installs'),
    path('api/usage/pageviews', views.api_usage_pageviews, name='api_usage_pageviews'),
    path('api/usage/health', views.api_usage_health, name='api_usage_health'),

    # Discovery (top-level, not v1-prefixed)
    path('api/version', views.api_version, name='api_version'),

    # Legacy JSON API — pre-existing shape kept for backward compatibility
    path('api/health', views.api_health, name='api_health'),
    path('api/install/targets', views.api_install_targets, name='api_install_targets'),
    path('api/skills', views.api_skill_list, name='api_skill_list'),
    path('api/skills/<str:name>', views.api_skill_detail, name='api_skill_detail'),
    path('api/skills/<str:name>/zip', views.api_skill_zip, name='api_skill_zip'),
    path('api/skills/<str:name>/files', views.api_skill_files, name='api_skill_files'),
    path('api/skills/<str:name>/install', views.api_skill_install, name='api_skill_install'),
    path('api/skills/<str:name>/versions', views.api_versions, name='api_versions'),
    path('api/skills/<str:name>/versions/<str:version>', views.api_version_detail, name='api_version_detail'),
    path('api/skills/<str:name>/versions/<str:version>/install',
         views.api_version_install, name='api_version_install'),
    path('api/skills/<str:name>/versions/<str:version>/zip', views.api_version_zip, name='api_version_zip'),
    path('api/skills/<str:name>/versions/<str:version>/files', views.api_version_files, name='api_version_files'),
    path('api/install/targets/<str:target_name>/skills',
         views.api_installed_list, name='api_installed_list'),
    path('api/install/targets/<str:target_name>/skills/<str:name>/uninstall',
         views.api_installed_uninstall, name='api_installed_uninstall'),

    # v1 JSON API — {data, meta?, error?} envelope, structured error codes
    path('api/v1/health', views_v1.api_v1_health, name='api_v1_health'),
    path('api/v1/install/targets', views_v1.api_v1_install_targets, name='api_v1_install_targets'),
    path('api/v1/skills', views_v1.api_v1_skill_list, name='api_v1_skill_list'),
    path('api/v1/skills/<str:name>', views_v1.api_v1_skill_detail, name='api_v1_skill_detail'),
    path('api/v1/skills/<str:name>/zip', views_v1.api_v1_skill_zip, name='api_v1_skill_zip'),
    path('api/v1/skills/<str:name>/files', views_v1.api_v1_skill_files, name='api_v1_skill_files'),
    path('api/v1/skills/<str:name>/install', views_v1.api_v1_skill_install, name='api_v1_skill_install'),
    path('api/v1/skills/<str:name>/versions', views_v1.api_v1_versions, name='api_v1_versions'),
    path('api/v1/skills/<str:name>/versions/<str:version>',
         views_v1.api_v1_version_detail, name='api_v1_version_detail'),
    path('api/v1/skills/<str:name>/versions/<str:version>/install',
         views_v1.api_v1_version_install, name='api_v1_version_install'),
    path('api/v1/skills/<str:name>/versions/<str:version>/zip',
         views_v1.api_v1_version_zip, name='api_v1_version_zip'),
    path('api/v1/skills/<str:name>/versions/<str:version>/files',
         views_v1.api_v1_version_files, name='api_v1_version_files'),
    path('api/v1/install/targets/<str:target_name>/skills',
         views_v1.api_v1_installed_list, name='api_v1_installed_list'),
    path('api/v1/install/targets/<str:target_name>/skills/<str:name>/uninstall',
         views_v1.api_v1_installed_uninstall, name='api_v1_installed_uninstall'),
]
