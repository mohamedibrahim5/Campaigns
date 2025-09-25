from django.urls import path, include
from .views import (
    validate_token,
    broadcast,
    dashboard,
    broadcast_landing,
    broadcast_landing_bot,
    broadcast_landing_bot_token,
    upload_photo,
    bot_logs_html,
    bot_logs_pdf,
    bot_logs_html_token,
    bot_logs_pdf_token,
    send_to_chat,
    update_bot_profile,
    sync_bot_profile_to_telegram,
    fetch_bot_profile_from_telegram,
    create_bot,
    start_bot,
    stop_bot,
    assign_bot_to_campaign,
    telegram_webhook,
    set_webhook,
    staff_send_form,
    broadcast_all,
    debug_bot_users,
    test_webhook,     # Add this
    import_updates,
    broadcast_action,
    election_dashboard,
    public_landing,
    candidate_landing,
    candidate_landing_mobile,
    candidate_login,
    candidate_login_simple,
    candidate_dashboard,
    candidate_dashboard_me,
    candidate_support,
    candidate_ask,
    user_profile,
)

urlpatterns = [
    path('', dashboard, name='hub_dashboard'),
    path('landing/', broadcast_landing, name='hub_landing'),
    path('landing/<int:bot_id>/', broadcast_landing_bot, name='hub_landing_bot'),
    path('landing/token/<str:bot_token>/', broadcast_landing_bot_token, name='hub_landing_bot_token'),
    path('upload_photo/', upload_photo, name='hub_upload_photo'),
    path('logs/<int:bot_id>/', bot_logs_html, name='hub_logs_html'),
    path('logs/<int:bot_id>/pdf/', bot_logs_pdf, name='hub_logs_pdf'),
    path('logs/token/<str:bot_token>/', bot_logs_html_token, name='hub_logs_html_token'),
    path('logs/token/<str:bot_token>/pdf/', bot_logs_pdf_token, name='hub_logs_pdf_token'),
    path('send_to_chat/', send_to_chat, name='hub_send_to_chat'),
    path('bots/<int:bot_id>/update_profile/', update_bot_profile, name='hub_update_bot_profile'),
    path('bots/<int:bot_id>/sync_profile/', sync_bot_profile_to_telegram, name='hub_sync_bot_profile'),
    path('bots/<int:bot_id>/fetch_profile/', fetch_bot_profile_from_telegram, name='hub_fetch_bot_profile'),
    path('validate/', validate_token),
    path('broadcast/', broadcast),
    path('broadcast_all/', broadcast_all),
    path('broadcast_action/', broadcast_action),
    path('import_updates/', import_updates),
    path('bots/create/', create_bot),
    path('bots/start/', start_bot),
    path('bots/stop/', stop_bot),
    path('campaigns/assign/', assign_bot_to_campaign),
    path('bots/<int:bot_id>/webhook/', telegram_webhook),
    path('bots/set_webhook/', set_webhook),
    path('send/', staff_send_form, name='hub_send_form'),
    path('bots/<int:bot_id>/debug/', debug_bot_users),
    # Debug endpoints
    path('bots/<int:bot_id>/test/', test_webhook),
    
    # Election 360 SaaS
    path('election-dashboard/', election_dashboard, name='election_dashboard'),
    path('election/', include('hub.election_urls')),
    
    # Public landing page
    path('public/', public_landing, name='public_landing'),
    
    # Candidate login and dashboards
    path('candidate/login/', candidate_login_simple, name='candidate_login_simple'),
    path('candidate/dashboard/', candidate_dashboard_me, name='candidate_dashboard_me'),
    
    # Candidate landing pages (must come after the non-parameterized routes above)
    path('candidate/<str:candidate_id>/', candidate_landing, name='candidate_landing'),
    path('candidate/<str:candidate_id>/mobile/', candidate_landing_mobile, name='candidate_landing_mobile'),
    path('candidate/<str:candidate_id>/support/', candidate_support, name='candidate_support'),
    path('candidate/<str:candidate_id>/ask/', candidate_ask, name='candidate_ask'),
    path('candidate/<str:candidate_id>/login/', candidate_login, name='candidate_login'),
    path('candidate/<str:candidate_id>/dashboard/', candidate_dashboard, name='candidate_dashboard'),
    
    # User profile (redirects to election dashboard)
    path('profile/', user_profile, name='user_profile'),
    
    # Direct mobile landing page for ahmed
]