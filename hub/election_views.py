"""
Election 360 SaaS API Views
"""
import json
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import (
    Candidate, Event, EventAttendance, Speech, Poll, PollResponse, 
    Supporter, Volunteer, VolunteerActivity, FakeNewsAlert, DailyQuestion,
    CampaignAnalytics, BotUser
)


# ===== CANDIDATE MANAGEMENT =====

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def candidates_list(request):
    """List all candidates or create a new one"""
    if request.method == 'GET':
        candidates = Candidate.objects.filter(is_active=True).order_by('-created_at')
        data = []
        for candidate in candidates:
            data.append({
                'id': str(candidate.id),
                'name': candidate.name,
                'position': candidate.position,
                'party': candidate.party,
                'profile_image': candidate.profile_image.url if candidate.profile_image else None,
                'logo': candidate.logo.url if candidate.logo else None,
                'created_at': candidate.created_at,
            })
        return Response(data)
    
    elif request.method == 'POST':
        data = request.data
        candidate = Candidate.objects.create(
            name=data.get('name'),
            position=data.get('position'),
            party=data.get('party'),
            bio=data.get('bio'),
            program=data.get('program'),
            website=data.get('website'),
            email=data.get('email'),
            phone=data.get('phone'),
            social_media=data.get('social_media', {}),
            created_by=request.user
        )
        return Response({
            'id': str(candidate.id),
            'name': candidate.name,
            'position': candidate.position,
            'created_at': candidate.created_at,
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def candidate_detail(request, candidate_id):
    """Get, update, or delete a specific candidate"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response({
            'id': str(candidate.id),
            'name': candidate.name,
            'position': candidate.position,
            'party': candidate.party,
            'bio': candidate.bio,
            'program': candidate.program,
            'profile_image': candidate.profile_image.url if candidate.profile_image else None,
            'logo': candidate.logo.url if candidate.logo else None,
            'website': candidate.website,
            'email': candidate.email,
            'phone': candidate.phone,
            'social_media': candidate.social_media,
            'is_active': candidate.is_active,
            'created_at': candidate.created_at,
            'updated_at': candidate.updated_at,
        })
    
    elif request.method == 'PUT':
        data = request.data
        for field in ['name', 'position', 'party', 'bio', 'program', 'website', 'email', 'phone', 'social_media']:
            if field in data:
                setattr(candidate, field, data[field])
        candidate.save()
        return Response({'message': 'Candidate updated successfully'})
    
    elif request.method == 'DELETE':
        candidate.is_active = False
        candidate.save()
        return Response({'message': 'Candidate deactivated successfully'})


# ===== EVENTS & ANNOUNCEMENTS =====

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def events_list(request, candidate_id):
    """List events for a candidate or create a new event"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        events = candidate.events.filter(is_public=True).order_by('-start_datetime')
        data = []
        for event in events:
            data.append({
                'id': str(event.id),
                'title': event.title,
                'description': event.description,
                'event_type': event.event_type,
                'location': event.location,
                'latitude': float(event.latitude) if event.latitude else None,
                'longitude': float(event.longitude) if event.longitude else None,
                'start_datetime': event.start_datetime,
                'end_datetime': event.end_datetime,
                'max_attendees': event.max_attendees,
                'image': event.image.url if event.image else None,
                'created_at': event.created_at,
            })
        return Response(data)
    
    elif request.method == 'POST':
        data = request.data
        event = Event.objects.create(
            candidate=candidate,
            title=data.get('title'),
            description=data.get('description'),
            event_type=data.get('event_type', 'meeting'),
            location=data.get('location'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            start_datetime=data.get('start_datetime'),
            end_datetime=data.get('end_datetime'),
            max_attendees=data.get('max_attendees'),
        )
        return Response({
            'id': str(event.id),
            'title': event.title,
            'start_datetime': event.start_datetime,
            'created_at': event.created_at,
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@csrf_exempt
def register_event_attendance(request, event_id):
    """Register attendance for an event via bot"""
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)
    
    data = json.loads(request.body.decode('utf-8') or '{}')
    telegram_id = data.get('telegram_id')
    bot_id = data.get('bot_id')
    
    if not telegram_id or not bot_id:
        return JsonResponse({'error': 'telegram_id and bot_id required'}, status=400)
    
    try:
        bot_user = BotUser.objects.get(bot_id=bot_id, telegram_id=telegram_id)
    except BotUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    attendance, created = EventAttendance.objects.get_or_create(
        event=event,
        bot_user=bot_user,
        defaults={'notes': data.get('notes', '')}
    )
    
    return JsonResponse({
        'attended': True,
        'created': created,
        'attended_at': attendance.attended_at,
    })


# ===== AI SPEECH WRITER =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_speech(request, candidate_id):
    """Generate AI speech from candidate ideas"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    data = request.data
    ideas = data.get('ideas', '')
    title = data.get('title', 'Speech')
    event_id = data.get('event_id')
    
    if not ideas:
        return Response({'error': 'Ideas are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # TODO: Integrate with AI API (OpenAI, etc.)
    # For now, create a placeholder speech
    full_speech = f"""
    Ladies and gentlemen,
    
    {ideas}
    
    Thank you for your attention.
    """
    
    summary = f"Key points: {ideas[:200]}..."
    facebook_post = f"🎤 {title}\n\n{summary}\n\n#Election2024 #{candidate.name.replace(' ', '')}"
    twitter_post = f"🎤 {title}\n\n{summary}\n\n#Election2024"
    
    event = None
    if event_id:
        try:
            event = Event.objects.get(id=event_id, candidate=candidate)
        except Event.DoesNotExist:
            pass
    
    speech = Speech.objects.create(
        candidate=candidate,
        title=title,
        ideas=ideas,
        full_speech=full_speech,
        summary=summary,
        facebook_post=facebook_post,
        twitter_post=twitter_post,
        event=event,
    )
    
    return Response({
        'id': str(speech.id),
        'title': speech.title,
        'full_speech': speech.full_speech,
        'summary': speech.summary,
        'facebook_post': speech.facebook_post,
        'twitter_post': speech.twitter_post,
        'created_at': speech.created_at,
    }, status=status.HTTP_201_CREATED)


# ===== POLLS & SURVEYS =====

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def polls_list(request, candidate_id):
    """List polls for a candidate or create a new poll"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        polls = candidate.polls.filter(is_active=True).order_by('-created_at')
        data = []
        for poll in polls:
            data.append({
                'id': str(poll.id),
                'title': poll.title,
                'question': poll.question,
                'options': poll.options,
                'is_anonymous': poll.is_anonymous,
                'allows_multiple_answers': poll.allows_multiple_answers,
                'expires_at': poll.expires_at,
                'created_at': poll.created_at,
            })
        return Response(data)
    
    elif request.method == 'POST':
        data = request.data
        poll = Poll.objects.create(
            candidate=candidate,
            title=data.get('title'),
            question=data.get('question'),
            options=data.get('options', []),
            is_anonymous=data.get('is_anonymous', True),
            allows_multiple_answers=data.get('allows_multiple_answers', False),
            expires_at=data.get('expires_at'),
        )
        return Response({
            'id': str(poll.id),
            'title': poll.title,
            'question': poll.question,
            'options': poll.options,
            'created_at': poll.created_at,
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@csrf_exempt
def submit_poll_response(request, poll_id):
    """Submit a poll response via bot"""
    try:
        poll = Poll.objects.get(id=poll_id)
    except Poll.DoesNotExist:
        return JsonResponse({'error': 'Poll not found'}, status=404)
    
    data = json.loads(request.body.decode('utf-8') or '{}')
    telegram_id = data.get('telegram_id')
    bot_id = data.get('bot_id')
    selected_options = data.get('selected_options', [])
    
    if not telegram_id or not bot_id or not selected_options:
        return JsonResponse({'error': 'telegram_id, bot_id, and selected_options required'}, status=400)
    
    try:
        bot_user = BotUser.objects.get(bot_id=bot_id, telegram_id=telegram_id)
    except BotUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    response, created = PollResponse.objects.get_or_create(
        poll=poll,
        bot_user=bot_user,
        defaults={'selected_options': selected_options}
    )
    
    if not created:
        response.selected_options = selected_options
        response.save()
    
    return JsonResponse({
        'responded': True,
        'created': created,
        'responded_at': response.responded_at,
    })


# ===== SUPPORTER REGISTRATION =====

@api_view(['POST'])
@csrf_exempt
def register_supporter(request, candidate_id):
    """Register a supporter via bot"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return JsonResponse({'error': 'Candidate not found'}, status=404)
    
    data = json.loads(request.body.decode('utf-8') or '{}')
    telegram_id = data.get('telegram_id')
    bot_id = data.get('bot_id')
    city = data.get('city')
    district = data.get('district')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    support_level = data.get('support_level', 5)
    
    if not telegram_id or not bot_id:
        return JsonResponse({'error': 'telegram_id and bot_id required'}, status=400)
    
    try:
        bot_user = BotUser.objects.get(bot_id=bot_id, telegram_id=telegram_id)
    except BotUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    supporter, created = Supporter.objects.get_or_create(
        candidate=candidate,
        bot_user=bot_user,
        defaults={
            'city': city,
            'district': district,
            'latitude': latitude,
            'longitude': longitude,
            'support_level': support_level,
            'notes': data.get('notes', ''),
        }
    )
    
    if not created:
        # Update existing supporter
        supporter.city = city or supporter.city
        supporter.district = district or supporter.district
        supporter.latitude = latitude or supporter.latitude
        supporter.longitude = longitude or supporter.longitude
        supporter.support_level = support_level
        supporter.notes = data.get('notes', supporter.notes)
        supporter.save()
    
    return JsonResponse({
        'registered': True,
        'created': created,
        'support_level': supporter.support_level,
        'registered_at': supporter.registered_at,
    })


# ===== HEATMAP DATA =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supporter_heatmap(request, candidate_id):
    """Get supporter data for heatmap visualization"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    supporters = candidate.supporters.filter(
        latitude__isnull=False,
        longitude__isnull=False
    ).values('latitude', 'longitude', 'city', 'district', 'support_level')
    
    # Group by city for summary
    city_stats = candidate.supporters.values('city').annotate(
        count=Count('id'),
        avg_support=Count('support_level')
    ).order_by('-count')
    
    return Response({
        'supporters': list(supporters),
        'city_stats': list(city_stats),
        'total_supporters': candidate.supporters.count(),
    })


# ===== VOLUNTEER MANAGEMENT =====

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def volunteers_list(request, candidate_id):
    """List volunteers for a candidate or register a new volunteer"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        volunteers = candidate.volunteers.filter(is_active=True).order_by('-joined_at')
        data = []
        for volunteer in volunteers:
            total_points = sum(activity.points_earned for activity in volunteer.activities.all())
            data.append({
                'id': str(volunteer.id),
                'name': volunteer.name,
                'role': volunteer.role,
                'phone': volunteer.phone,
                'email': volunteer.email,
                'total_points': total_points,
                'joined_at': volunteer.joined_at,
                'last_activity': volunteer.last_activity,
            })
        return Response(data)
    
    elif request.method == 'POST':
        data = request.data
        telegram_id = data.get('telegram_id')
        bot_id = data.get('bot_id')
        
        if not telegram_id or not bot_id:
            return Response({'error': 'telegram_id and bot_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            bot_user = BotUser.objects.get(bot_id=bot_id, telegram_id=telegram_id)
        except BotUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        volunteer, created = Volunteer.objects.get_or_create(
            candidate=candidate,
            bot_user=bot_user,
            defaults={
                'name': data.get('name', f"{bot_user.first_name} {bot_user.last_name}".strip()),
                'phone': data.get('phone', bot_user.phone_number),
                'email': data.get('email'),
                'role': data.get('role', 'volunteer'),
            }
        )
        
        return Response({
            'id': str(volunteer.id),
            'name': volunteer.name,
            'role': volunteer.role,
            'created': created,
            'joined_at': volunteer.joined_at,
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_volunteer_activity(request, volunteer_id):
    """Log volunteer activity for gamification"""
    try:
        volunteer = Volunteer.objects.get(id=volunteer_id)
    except Volunteer.DoesNotExist:
        return Response({'error': 'Volunteer not found'}, status=status.HTTP_404_NOT_FOUND)
    
    data = request.data
    activity_type = data.get('activity_type')
    description = data.get('description', '')
    supporters_contacted = data.get('supporters_contacted', 0)
    posters_distributed = data.get('posters_distributed', 0)
    hours_worked = data.get('hours_worked', 0)
    location = data.get('location', '')
    
    # Calculate points based on activity type
    points_config = settings.ELECTION_360.get('VOLUNTEER_POINTS', {})
    base_points = points_config.get(activity_type, 5)
    points_earned = base_points + (supporters_contacted * 2) + (posters_distributed * 1) + (hours_worked * 3)
    
    activity = VolunteerActivity.objects.create(
        volunteer=volunteer,
        activity_type=activity_type,
        description=description,
        supporters_contacted=supporters_contacted,
        posters_distributed=posters_distributed,
        hours_worked=hours_worked,
        points_earned=points_earned,
        location=location,
    )
    
    # Update volunteer's last activity
    volunteer.last_activity = timezone.now()
    volunteer.save()
    
    return Response({
        'id': str(activity.id),
        'activity_type': activity.activity_type,
        'points_earned': activity.points_earned,
        'created_at': activity.created_at,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def volunteer_leaderboard(request, candidate_id):
    """Get volunteer leaderboard for a candidate"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    volunteers = candidate.volunteers.filter(is_active=True)
    leaderboard = []
    
    for volunteer in volunteers:
        total_points = sum(activity.points_earned for activity in volunteer.activities.all())
        total_activities = volunteer.activities.count()
        leaderboard.append({
            'name': volunteer.name,
            'role': volunteer.role,
            'total_points': total_points,
            'total_activities': total_activities,
            'joined_at': volunteer.joined_at,
        })
    
    # Sort by total points
    leaderboard.sort(key=lambda x: x['total_points'], reverse=True)
    
    return Response(leaderboard)


# ===== FAKE NEWS MONITORING =====

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def fake_news_alerts(request, candidate_id):
    """List fake news alerts or create a new one"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        alerts = candidate.fake_news_alerts.filter(is_resolved=False).order_by('-detected_at')
        data = []
        for alert in alerts:
            data.append({
                'id': str(alert.id),
                'title': alert.title,
                'content': alert.content,
                'source_url': alert.source_url,
                'source_platform': alert.source_platform,
                'severity': alert.severity,
                'is_verified': alert.is_verified,
                'detected_at': alert.detected_at,
            })
        return Response(data)
    
    elif request.method == 'POST':
        data = request.data
        alert = FakeNewsAlert.objects.create(
            candidate=candidate,
            title=data.get('title'),
            content=data.get('content'),
            source_url=data.get('source_url'),
            source_platform=data.get('source_platform', 'unknown'),
            severity=data.get('severity', 'medium'),
        )
        return Response({
            'id': str(alert.id),
            'title': alert.title,
            'severity': alert.severity,
            'detected_at': alert.detected_at,
        }, status=status.HTTP_201_CREATED)


# ===== DAILY Q&A =====

@api_view(['GET', 'POST'])
@csrf_exempt
def daily_questions(request, candidate_id):
    """List daily questions or submit a new question"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return JsonResponse({'error': 'Candidate not found'}, status=404)
    
    if request.method == 'GET':
        questions = candidate.daily_questions.filter(is_public=True).order_by('-asked_at')
        data = []
        for question in questions:
            data.append({
                'id': str(question.id),
                'question': question.question,
                'answer': question.answer,
                'is_answered': question.is_answered,
                'asked_at': question.asked_at,
                'answered_at': question.answered_at,
            })
        return JsonResponse({'questions': data})
    
    elif request.method == 'POST':
        data = json.loads(request.body.decode('utf-8') or '{}')
        telegram_id = data.get('telegram_id')
        bot_id = data.get('bot_id')
        question_text = data.get('question')
        
        if not telegram_id or not bot_id or not question_text:
            return JsonResponse({'error': 'telegram_id, bot_id, and question required'}, status=400)
        
        try:
            bot_user = BotUser.objects.get(bot_id=bot_id, telegram_id=telegram_id)
        except BotUser.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        question = DailyQuestion.objects.create(
            candidate=candidate,
            bot_user=bot_user,
            question=question_text,
        )
        
        return JsonResponse({
            'id': str(question.id),
            'question': question.question,
            'asked_at': question.asked_at,
        }, status=201)


# ===== ANALYTICS & REPORTS =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_analytics(request, candidate_id):
    """Get comprehensive campaign analytics"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get or create analytics
    analytics, created = CampaignAnalytics.objects.get_or_create(candidate=candidate)
    
    # Update analytics
    analytics.total_supporters = candidate.supporters.count()
    analytics.total_volunteers = candidate.volunteers.filter(is_active=True).count()
    analytics.total_events = candidate.events.count()
    analytics.total_polls = candidate.polls.count()
    analytics.total_speeches = candidate.speeches.count()
    analytics.total_fake_news_alerts = candidate.fake_news_alerts.count()
    analytics.save()
    
    # Additional metrics
    recent_events = candidate.events.filter(
        start_datetime__gte=timezone.now() - timezone.timedelta(days=30)
    ).count()
    
    active_polls = candidate.polls.filter(is_active=True).count()
    
    supporters_by_city = candidate.supporters.values('city').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    return Response({
        'candidate_name': candidate.name,
        'total_supporters': analytics.total_supporters,
        'total_volunteers': analytics.total_volunteers,
        'total_events': analytics.total_events,
        'total_polls': analytics.total_polls,
        'total_speeches': analytics.total_speeches,
        'total_fake_news_alerts': analytics.total_fake_news_alerts,
        'recent_events_30_days': recent_events,
        'active_polls': active_polls,
        'supporters_by_city': list(supporters_by_city),
        'last_updated': analytics.last_updated,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_supporters_report(request, candidate_id):
    """Export supporters report as JSON"""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({'error': 'Candidate not found'}, status=status.HTTP_404_NOT_FOUND)
    
    supporters = candidate.supporters.select_related('bot_user').order_by('-registered_at')
    data = []
    
    for supporter in supporters:
        data.append({
            'name': f"{supporter.bot_user.first_name} {supporter.bot_user.last_name}".strip(),
            'phone': supporter.bot_user.phone_number,
            'city': supporter.city,
            'district': supporter.district,
            'support_level': supporter.support_level,
            'registered_at': supporter.registered_at,
            'notes': supporter.notes,
        })
    
    return Response({
        'candidate_name': candidate.name,
        'export_date': timezone.now(),
        'total_supporters': len(data),
        'supporters': data,
    })
