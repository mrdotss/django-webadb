from django.urls import path
from apps.home import views
from apps.caf.cold_action import getDevices, getLogcat, postShell, postKey, postText, getScreenshot, simulate_touch

urlpatterns = [

    # The home page
    path('', views.Dashboard.as_view(), name='dashboard'),

    # The case page
    path('case/', views.CaseListView.as_view(), name='cases_home'),
    path('case/create', views.CaseCreateView.as_view(), name='cases_create'),
    path('case/update/<uuid:case_id>', views.CaseUpdateView.as_view(), name='cases_update'),
    path('case/<uuid:case_id>/delete', views.CaseDeleteView.as_view(), name='cases_delete'),

    # The evidence page
    path('evidence/', views.EvidenceListView.as_view(), name='evidences_home'),
    path('evidence/create', views.EvidenceCreateView.as_view(), name='evidences_create'),
    path('evidence/update/<uuid:evidence_id>', views.EvidenceUpdateView.as_view(), name='evidences_update'),
    path('evidence/<uuid:evidence_id>/delete', views.EvidenceDeleteView.as_view(), name='evidences_delete'),
    path('evidence/get_case_members/<uuid:case_id>', views.get_case_members, name='get_case_members'),
    path('evidence/get_case_members_by_evidence/<uuid:evidence_id>', views.get_case_members_by_evidence, name='get_case_members_by_evidence'),

    # The activities page
    path('activities/', views.activitiesList, name='activities_home'),
    path('activities/ajax/', views.activitiesAjax, name='activities_ajax'),

    path('device/', views.Devices.as_view(), name='devices_home'),
    path('device/detail/<str:dev_id>', views.DevicesDetail.as_view(), name='devices_detail'),
    path('analyst-report/', views.Analysts.as_view(), name='report_analyst_home'),
    path('profile/', views.Profiles.as_view(), name='profile_home'),
    path('device/acquisition/<str:serial_id>', views.Acquisitions.as_view(), name='device_acquisition'),
    path('device/acquisition/<str:serial_id>/setup/<uuid:unique_code>', views.AcquisitionSetup.as_view(), name='device_acquisition_setup'),

    # Generate unique code
    path('device/acquisition/<str:serial_id>/generate-unique-code/<str:acquire_method>', views.GenerateUniqueCodeView.as_view(), name='generate_unique_code'),

    ## No Class
    path('evidence/<uuid:evidence_id>/coc', views.get_evidence_coc, name='get_evidence_coc'),
    path('evidence/<uuid:evidence_id>/acquisition_history', views.get_evidence_acquisition_history, name='get_evidence_acquisition_history'),
    path('acquisition-setup/<str:serial_id>/save-location/<uuid:unique_link>', views.get_acquisition_save_location,
         name='device_acquisition_save_location'),
    path('acquisition-setup/<str:serial_id>/pre-progress/<uuid:unique_link>', views.get_acquisition_presetup,
         name='device_acquisition_pre_setup'),
    path('acquisition-setup/<str:serial_id>/progress/<uuid:unique_link>', views.get_acquisition_setup,
         name='device_acquisition_setup'),

    path('device/api/detail/<str:id>', getDevices),
    path('device/logcat/<str:id>', getLogcat),
    path('device/shell/<str:id>', postShell),
    path('device/key/<str:id>', postKey),
    path('device/text/<str:id>', postText),
    path('device/screenshot/<str:id>', getScreenshot),
    path('device/simulate_touch/<str:device_id>', simulate_touch),

]
