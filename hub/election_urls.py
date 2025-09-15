"""
Election 360 SaaS URL Patterns
"""
from django.urls import path
from . import election_views

app_name = 'election'

urlpatterns = [
    # Candidate Management
    path('candidates/', election_views.candidates_list, name='candidates_list'),
    path('candidates/<uuid:candidate_id>/', election_views.candidate_detail, name='candidate_detail'),
    
    # Events & Announcements
    path('candidates/<uuid:candidate_id>/events/', election_views.events_list, name='events_list'),
    path('events/<uuid:event_id>/attendance/', election_views.register_event_attendance, name='register_attendance'),
    
    # AI Speech Writer
    path('candidates/<uuid:candidate_id>/speeches/generate/', election_views.generate_speech, name='generate_speech'),
    
    # Polls & Surveys
    path('candidates/<uuid:candidate_id>/polls/', election_views.polls_list, name='polls_list'),
    path('polls/<uuid:poll_id>/respond/', election_views.submit_poll_response, name='submit_poll_response'),
    
    # Supporter Registration
    path('candidates/<uuid:candidate_id>/supporters/register/', election_views.register_supporter, name='register_supporter'),
    path('candidates/<uuid:candidate_id>/heatmap/', election_views.supporter_heatmap, name='supporter_heatmap'),
    
    # Volunteer Management
    path('candidates/<uuid:candidate_id>/volunteers/', election_views.volunteers_list, name='volunteers_list'),
    path('volunteers/<uuid:volunteer_id>/activities/', election_views.log_volunteer_activity, name='log_volunteer_activity'),
    path('candidates/<uuid:candidate_id>/leaderboard/', election_views.volunteer_leaderboard, name='volunteer_leaderboard'),
    
    # Fake News Monitoring
    path('candidates/<uuid:candidate_id>/fake-news/', election_views.fake_news_alerts, name='fake_news_alerts'),
    
    # Daily Q&A
    path('candidates/<uuid:candidate_id>/questions/', election_views.daily_questions, name='daily_questions'),
    
    # Analytics & Reports
    path('candidates/<uuid:candidate_id>/analytics/', election_views.campaign_analytics, name='campaign_analytics'),
    path('candidates/<uuid:candidate_id>/export/supporters/', election_views.export_supporters_report, name='export_supporters_report'),
]
