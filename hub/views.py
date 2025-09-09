import json
import requests
import logging
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .models import Bot, Campaign, CampaignAssignment, BotUser, SendLog, WebhookEvent, MessageLog
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import StreamingHttpResponse
import mimetypes

# Set up logging
logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(['POST'])
def validate_token(request):
    data = json.loads(request.body.decode('utf-8') or "{}")
    token = (data.get('bot_token') or "").strip()
    if not token:
        return JsonResponse({"error": "bot_token required"}, status=400)
    r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    try:
        js = r.json()
    except Exception:
        js = {"ok": False, "status_code": r.status_code}
    return JsonResponse(js, status=200 if js.get('ok') else 400)


@csrf_exempt
@require_http_methods(['POST'])
def broadcast(request):
    data = json.loads(request.body.decode('utf-8') or "{}")
    token = (data.get('bot_token') or "").strip()
    chat_id = (data.get('chat_id') or "").strip()
    text = (data.get('text') or "").strip()
    if not token or not chat_id or not text:
        return JsonResponse({"error": "bot_token, chat_id, text required"}, status=400)
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }, timeout=15)
    try:
        js = r.json()
    except Exception:
        js = {"ok": False, "status_code": r.status_code}
    return JsonResponse(js, status=200 if js.get('ok') else 400)


def dashboard(request: HttpRequest) -> HttpResponse:
    bots = Bot.objects.order_by('-created_at')[:50]
    campaigns = Campaign.objects.order_by('-created_at')[:50]
    context = {
        'bots': bots,
        'campaigns': campaigns,
    }
    return render(request, 'hub/dashboard.html', context)


@login_required()
def broadcast_landing(request: HttpRequest) -> HttpResponse:
    """Landing page index: shows bot selection (for compatibility)."""
    bots = Bot.objects.order_by('-created_at')
    return render(request, 'hub/landing.html', {'bots': bots})


@login_required()
def broadcast_landing_bot(request: HttpRequest, bot_id: int) -> HttpResponse:
    """Per-bot landing page; access controlled by simple mapping rules."""
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return HttpResponse(status=404)

    # Access control mapping:
    # - Superuser can access ANY bot
    # - Non-superuser (e.g., staff/normal) can access bot 2 only
    # - Others: forbidden
    user = request.user
    allowed = False
    if user.is_superuser:
        allowed = True
    elif not user.is_superuser and bot_id == 2:
        allowed = True

    if not allowed:
        return HttpResponse("Forbidden", status=403)

    return render(request, 'hub/landing.html', {'bot': bot})


@csrf_exempt
@login_required()
@require_POST
def upload_photo(request: HttpRequest) -> JsonResponse:
    """Accept a file upload and return its public media URL."""
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'file required'}, status=400)
    # Save under media/uploads/
    path = default_storage.save(f"uploads/{timezone.now().strftime('%Y%m%d_%H%M%S')}_{f.name}", ContentFile(f.read()))
    url = request.build_absolute_uri(settings.MEDIA_URL + path.split('uploads/')[-1] if path.startswith('uploads/') else settings.MEDIA_URL + path)
    # Build correct URL when using default_storage (FileSystemStorage)
    if hasattr(default_storage, 'url'):
        try:
            url = request.build_absolute_uri(default_storage.url(path))
        except Exception:
            pass
    return JsonResponse({'ok': True, 'url': url, 'path': path})


@login_required()
def bot_logs_html(request: HttpRequest, bot_id: int) -> HttpResponse:
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return HttpResponse(status=404)
    # Access control mirrors landing access
    user = request.user
    if not (user.is_superuser or (not user.is_superuser and bot_id == 2)):
        return HttpResponse("Forbidden", status=403)
    logs = MessageLog.objects.filter(bot=bot).order_by('-received_at')[:500]
    return render(request, 'hub/logs.html', {'bot': bot, 'logs': logs})


@login_required()
def bot_logs_pdf(request: HttpRequest, bot_id: int):
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return HttpResponse(status=404)
    user = request.user
    if not (user.is_superuser or (not user.is_superuser and bot_id == 2)):
        return HttpResponse("Forbidden", status=403)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
    except Exception:
        return JsonResponse({'error': 'PDF export requires reportlab. Install with: pip install reportlab'}, status=501)

    logs = MessageLog.objects.filter(bot=bot).order_by('-received_at')[:1000]

    def pdf_generator():
        from io import BytesIO
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        margin = 15 * mm
        y = height - margin
        title = f"Message Logs for {bot.name}"
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, title)
        y -= 12 * mm
        c.setFont("Helvetica", 9)
        for log in logs:
            line = f"{log.received_at.strftime('%Y-%m-%d %H:%M:%S')} | chat={log.chat_id} | msg={log.message_id or '-'} | { (log.text or '')[:1000] }"
            # Wrap long lines
            max_width = width - 2 * margin
            words = line.split(' ')
            current = ''
            for w in words:
                test = (current + (' ' if current else '') + w)
                if c.stringWidth(test, "Helvetica", 9) <= max_width:
                    current = test
                else:
                    if y < margin + 20:
                        c.showPage()
                        y = height - margin
                        c.setFont("Helvetica", 9)
                    c.drawString(margin, y, current)
                    y -= 12
                    current = w
            if current:
                if y < margin + 20:
                    c.showPage()
                    y = height - margin
                    c.setFont("Helvetica", 9)
                c.drawString(margin, y, current)
                y -= 14
        c.showPage()
        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        yield pdf

    response = StreamingHttpResponse(pdf_generator(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bot_{bot_id}_logs.pdf"'
    return response


@csrf_exempt
@require_http_methods(['POST'])
def send_to_chat(request: HttpRequest) -> JsonResponse:
    """Send a text message to a specific chat for a given bot."""
    data = json.loads(request.body.decode('utf-8') or '{}')
    bot_id = data.get('bot_id')
    bot_token = (data.get('bot_token') or '').strip()
    chat_id = (data.get('chat_id') or '').strip()
    text = (data.get('text') or '').strip()

    if not chat_id or not text:
        return JsonResponse({'error': 'chat_id and text required'}, status=400)

    bot = None
    if bot_id:
        try:
            bot = Bot.objects.get(id=bot_id)
        except Bot.DoesNotExist:
            return JsonResponse({'error': 'bot not found'}, status=404)
    elif bot_token:
        bot = Bot.objects.filter(token=bot_token).first()
        if not bot:
            return JsonResponse({'error': 'bot not found for token'}, status=404)
    else:
        return JsonResponse({'error': 'bot_id or bot_token required'}, status=400)

    resp = requests.post(
        f"https://api.telegram.org/bot{bot.token}/sendMessage",
        json={'chat_id': chat_id, 'text': text, 'disable_web_page_preview': True},
        timeout=15,
    )
    try:
        js = resp.json()
    except Exception:
        js = {'ok': False, 'description': 'Invalid response'}

    # log
    try:
        bot_user = BotUser.objects.filter(bot=bot, telegram_id=int(chat_id)).first()
    except Exception:
        bot_user = None
    if not bot_user:
        try:
            bot_user = BotUser.objects.create(bot=bot, telegram_id=int(chat_id))
        except Exception:
            bot_user = None
    if bot_user:
        SendLog.objects.create(
            campaign=None,
            bot_user=bot_user,
            status=SendLog.STATUS_SENT if js.get('ok') else SendLog.STATUS_FAILED,
            message_id=str((js.get('result') or {}).get('message_id')) if js.get('ok') else None,
            error=None if js.get('ok') else (js.get('description') or 'Unknown error'),
            sent_at=timezone.now() if js.get('ok') else None,
        )

    return JsonResponse(js, status=200 if js.get('ok') else 400)


@csrf_exempt
@login_required()
@require_POST
def update_bot_profile(request: HttpRequest, bot_id: int) -> JsonResponse:
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return JsonResponse({'error': 'bot not found'}, status=404)

    # Only allow superusers or (non-superuser with bot_id==2) as per access rules
    user = request.user
    if not (user.is_superuser or (not user.is_superuser and bot_id == 2)):
        return JsonResponse({'error': 'forbidden'}, status=403)

    data = json.loads(request.body.decode('utf-8') or '{}')
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    image_url = (data.get('image_url') or '').strip()

    updates = []
    if name and bot.name != name:
        bot.name = name
        updates.append('name')
    # description and image can be cleared by sending empty string
    if 'description' in data and bot.description != description:
        bot.description = description or None
        updates.append('description')
    if 'image_url' in data and bot.image_url != image_url:
        bot.image_url = image_url or None
        updates.append('image_url')

    if updates:
        bot.save(update_fields=updates)

    return JsonResponse({'ok': True, 'updated': updates, 'bot': {
        'id': bot.id,
        'name': bot.name,
        'description': bot.description,
        'image_url': bot.image_url,
    }})


@csrf_exempt
@login_required()
@require_POST
def sync_bot_profile_to_telegram(request: HttpRequest, bot_id: int) -> JsonResponse:
    """Update bot profile on Telegram (name, description, short_description).
    Note: Telegram Bot API does not support changing the bot's profile photo programmatically; use @BotFather for that.
    """
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return JsonResponse({'error': 'bot not found'}, status=404)

    user = request.user
    if not (user.is_superuser or (not user.is_superuser and bot_id == 2)):
        return JsonResponse({'error': 'forbidden'}, status=403)

    data = json.loads(request.body.decode('utf-8') or '{}')
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    short_description = (data.get('short_description') or '').strip()

    results = {}

    # Update name
    if name:
        r = requests.post(
            f"https://api.telegram.org/bot{bot.token}/setMyName",
            json={'name': name}, timeout=15
        )
        try:
            results['setMyName'] = r.json()
        except Exception:
            results['setMyName'] = {'ok': False, 'description': 'Invalid response'}

    # Update description
    if description or ('description' in data):
        # Telegram max 512 chars
        desc = description[:512] if description else ''
        r = requests.post(
            f"https://api.telegram.org/bot{bot.token}/setMyDescription",
            json={'description': desc}, timeout=15
        )
        try:
            results['setMyDescription'] = r.json()
        except Exception:
            results['setMyDescription'] = {'ok': False, 'description': 'Invalid response'}

    # Update short description
    if short_description or ('short_description' in data):
        # Telegram max 120 chars
        sdesc = short_description[:120] if short_description else ''
        r = requests.post(
            f"https://api.telegram.org/bot{bot.token}/setMyShortDescription",
            json={'short_description': sdesc}, timeout=15
        )
        try:
            results['setMyShortDescription'] = r.json()
        except Exception:
            results['setMyShortDescription'] = {'ok': False, 'description': 'Invalid response'}

    return JsonResponse({'ok': True, 'results': results})


@login_required()
@require_http_methods(['GET'])
def fetch_bot_profile_from_telegram(request: HttpRequest, bot_id: int) -> JsonResponse:
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return JsonResponse({'error': 'bot not found'}, status=404)

    user = request.user
    if not (user.is_superuser or (not user.is_superuser and bot_id == 2)):
        return JsonResponse({'error': 'forbidden'}, status=403)

    out = {}
    # getMyName
    try:
        r = requests.get(f"https://api.telegram.org/bot{bot.token}/getMyName", timeout=15)
        out['getMyName'] = r.json()
    except Exception as e:
        out['getMyName'] = {'ok': False, 'description': str(e)}
    # getMyDescription
    try:
        r = requests.get(f"https://api.telegram.org/bot{bot.token}/getMyDescription", timeout=15)
        out['getMyDescription'] = r.json()
    except Exception as e:
        out['getMyDescription'] = {'ok': False, 'description': str(e)}
    # getMyShortDescription
    try:
        r = requests.get(f"https://api.telegram.org/bot{bot.token}/getMyShortDescription", timeout=15)
        out['getMyShortDescription'] = r.json()
    except Exception as e:
        out['getMyShortDescription'] = {'ok': False, 'description': str(e)}

    # Normalize values for convenience
    name_val = ((out.get('getMyName') or {}).get('result') or {}).get('name')
    desc_val = ((out.get('getMyDescription') or {}).get('result') or {}).get('description')
    sdesc_val = ((out.get('getMyShortDescription') or {}).get('result') or {}).get('short_description')
    return JsonResponse({'ok': True, 'name': name_val, 'description': desc_val, 'short_description': sdesc_val, 'raw': out})


@csrf_exempt
@require_http_methods(['POST'])
def create_bot(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body.decode('utf-8') or "{}")
    name = (data.get('name') or '').strip()
    token = (data.get('bot_token') or '').strip()
    if not name or not token:
        return JsonResponse({'error': 'name and bot_token required'}, status=400)
    # Validate token with Telegram API
    r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    try:
        js = r.json()
    except Exception:
        js = {"ok": False}
    if not js.get('ok'):
        return JsonResponse({'error': 'Invalid bot token'}, status=400)
    bot, created = Bot.objects.get_or_create(token=token, defaults={'name': name})
    if not created and bot.name != name:
        bot.name = name
        bot.save(update_fields=['name'])
    return JsonResponse({'ok': True, 'id': bot.id, 'name': bot.name})


@csrf_exempt
@require_http_methods(['POST'])
def start_bot(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body.decode('utf-8') or "{}")
    bot_id = data.get('bot_id')
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return JsonResponse({'error': 'bot not found'}, status=404)
    bot.is_active = True
    bot.save(update_fields=['is_active'])
    return JsonResponse({'ok': True})


@csrf_exempt
@require_http_methods(['POST'])
def stop_bot(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body.decode('utf-8') or "{}")
    bot_id = data.get('bot_id')
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return JsonResponse({'error': 'bot not found'}, status=404)
    bot.is_active = False
    bot.save(update_fields=['is_active'])
    return JsonResponse({'ok': True})


@csrf_exempt
@require_http_methods(['POST'])
def assign_bot_to_campaign(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body.decode('utf-8') or "{}")
    bot_id = data.get('bot_id')
    campaign_id = data.get('campaign_id')
    try:
        bot = Bot.objects.get(id=bot_id)
        campaign = Campaign.objects.get(id=campaign_id)
    except (Bot.DoesNotExist, Campaign.DoesNotExist):
        return JsonResponse({'error': 'bot or campaign not found'}, status=404)
    assignment, _ = CampaignAssignment.objects.get_or_create(bot=bot, campaign=campaign)
    return JsonResponse({'ok': True, 'assignment_id': assignment.id})


@csrf_exempt
@require_http_methods(['POST'])
def telegram_webhook(request: HttpRequest, bot_id: int) -> JsonResponse:
    # Log the incoming request
    logger.info(f"Webhook received for bot_id: {bot_id}")
    print(f"=== WEBHOOK DEBUG START ===")
    print(f"Bot ID: {bot_id}")
    print(f"Request body: {request.body.decode('utf-8')}")
    
    try:
        bot = Bot.objects.get(id=bot_id)
        print(f"Bot found: {bot.name} (Active: {bot.is_active})")
    except Bot.DoesNotExist:
        print(f"Bot with ID {bot_id} not found!")
        return JsonResponse({'error': 'bot not found'}, status=404)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        print(f"Parsed payload: {json.dumps(payload, indent=2)}")
    except Exception as e:
        print(f"Error parsing payload: {e}")
        payload = {}

    # Persist event for debugging
    try:
        webhook_event = WebhookEvent.objects.create(bot=bot, event_type='update', payload=payload)
        print(f"WebhookEvent created: {webhook_event.id}")
    except Exception as e:
        print(f"Error creating WebhookEvent: {e}")

    # Extract message
    message = payload.get('message') or payload.get('edited_message') or {}
    print(f"Message data: {json.dumps(message, indent=2)}")

    # Persist message into MessageLog if present
    try:
        if message:
            chat = message.get('chat', {})
            from_user = message.get('from', {})
            chat_id = chat.get('id')
            bot_user = BotUser.objects.filter(bot=bot, telegram_id=chat_id).first() if chat_id else None
            MessageLog.objects.create(
                bot=bot,
                bot_user=bot_user,
                message_id=str(message.get('message_id')) if message.get('message_id') is not None else None,
                chat_id=chat_id or 0,
                from_user_id=from_user.get('id'),
                text=message.get('text'),
                raw=message,
            )
    except Exception as e:
        print(f"Error persisting MessageLog: {e}")

    # Check if this is a /start command
    text = (message.get('text') or '').strip()
    print(f"Message text: '{text}'")
    
    if text.startswith('/start'):
        print("=== PROCESSING /START COMMAND ===")
        
        # Get chat and user info
        chat = message.get('chat', {})
        from_user = message.get('from', {})
        chat_id = chat.get('id')
        
        print(f"Chat info: {json.dumps(chat, indent=2)}")
        print(f"From user info: {json.dumps(from_user, indent=2)}")
        print(f"Chat ID: {chat_id}")
        
        if not chat_id:
            print("ERROR: No chat_id found!")
            return JsonResponse({'ok': False, 'error': 'No chat_id'})
        
        # Send welcome message first
        try:
            welcome_response = requests.post(
                f"https://api.telegram.org/bot{bot.token}/sendMessage", 
                json={
                    'chat_id': chat_id,
                    'text': 'Welcome! You are now registered and can receive broadcasts.'
                }, 
                timeout=10
            )
            print(f"Welcome message status: {welcome_response.status_code}")
            print(f"Welcome message response: {welcome_response.text}")
        except Exception as e:
            print(f"Error sending welcome message: {e}")
        
        # Register/update user
        try:
            print(f"Creating/updating user with telegram_id: {chat_id}")
            
            # Use from_user data if available, otherwise use chat data
            user_data = {
                'username': from_user.get('username') or chat.get('username'),
                'first_name': from_user.get('first_name') or chat.get('first_name'),
                'last_name': from_user.get('last_name') or chat.get('last_name'),
                'language_code': from_user.get('language_code') or chat.get('language_code'),
                'started_at': timezone.now(),
                'last_seen_at': timezone.now(),
            }
            
            print(f"User data for creation: {user_data}")
            
            bot_user, created = BotUser.objects.get_or_create(
                bot=bot, 
                telegram_id=chat_id,
                defaults=user_data
            )
            
            if created:
                print(f"✓ NEW USER CREATED: ID={bot_user.id}, telegram_id={bot_user.telegram_id}")
            else:
                print(f"✓ EXISTING USER FOUND: ID={bot_user.id}, telegram_id={bot_user.telegram_id}")
                print(f"  - Current started_at: {bot_user.started_at}")
                print(f"  - Current is_blocked: {bot_user.is_blocked}")
                
                # Update user info and ensure started_at is set
                update_fields = []
                
                if not bot_user.started_at:
                    bot_user.started_at = timezone.now()
                    update_fields.append('started_at')
                    print("  - Setting started_at")
                
                # Update other fields
                for field, value in user_data.items():
                    if field in ['started_at', 'last_seen_at']:
                        continue
                    if value and getattr(bot_user, field) != value:
                        setattr(bot_user, field, value)
                        update_fields.append(field)
                        print(f"  - Updating {field} to {value}")
                
                # Always update last_seen_at
                bot_user.last_seen_at = timezone.now()
                update_fields.append('last_seen_at')
                
                # Unblock if blocked
                if bot_user.is_blocked:
                    bot_user.is_blocked = False
                    update_fields.append('is_blocked')
                    print("  - Unblocking user")
                
                if update_fields:
                    bot_user.save(update_fields=update_fields)
                    print(f"  - Updated fields: {update_fields}")
            
            # Verify the user was saved correctly
            saved_user = BotUser.objects.get(bot=bot, telegram_id=chat_id)
            print(f"✓ VERIFICATION: User saved with started_at={saved_user.started_at}, blocked={saved_user.is_blocked}")
            
            # Count total active users for this bot
            active_count = BotUser.objects.filter(
                bot=bot, 
                started_at__isnull=False, 
                is_blocked=False
            ).count()
            print(f"✓ Total active users for bot {bot.name}: {active_count}")
            
        except Exception as e:
            print(f"ERROR registering user: {e}")
            import traceback
            traceback.print_exc()
    
    else:
        print(f"Not a /start command, text was: '{text}'")
        
        # Still register/update user for any interaction
        if message:
            chat = message.get('chat', {})
            from_user = message.get('from', {})
            chat_id = chat.get('id')
            
            if chat_id:
                try:
                    bot_user, created = BotUser.objects.get_or_create(
                        bot=bot, 
                        telegram_id=chat_id,
                        defaults={
                            'username': from_user.get('username') or chat.get('username'),
                            'first_name': from_user.get('first_name') or chat.get('first_name'),
                            'last_name': from_user.get('last_name') or chat.get('last_name'),
                            'language_code': from_user.get('language_code'),
                            'last_seen_at': timezone.now(),
                        }
                    )
                    
                    if not created:
                        bot_user.last_seen_at = timezone.now()
                        bot_user.save(update_fields=['last_seen_at'])
                    
                    print(f"User interaction logged: {chat_id}")
                    
                except Exception as e:
                    print(f"Error logging user interaction: {e}")

    # Handle callback queries and other update types
    callback_query = payload.get('callback_query')
    if callback_query:
        from_user = callback_query.get('from', {})
        if from_user and from_user.get('id'):
            try:
                bot_user, created = BotUser.objects.get_or_create(
                    bot=bot, 
                    telegram_id=from_user['id'],
                    defaults={
                        'username': from_user.get('username'),
                        'first_name': from_user.get('first_name'),
                        'last_name': from_user.get('last_name'),
                        'language_code': from_user.get('language_code'),
                        'last_seen_at': timezone.now(),
                    }
                )
                if not created:
                    bot_user.last_seen_at = timezone.now()
                    bot_user.save(update_fields=['last_seen_at'])
                print(f"Callback query user logged: {from_user['id']}")
            except Exception as e:
                print(f"Error logging callback query user: {e}")

    # Handle my_chat_member (join/left events)
    my_chat_member = payload.get('my_chat_member')
    if my_chat_member:
        from_user = my_chat_member.get('from', {})
        chat = my_chat_member.get('chat', {})
        
        if from_user and from_user.get('id'):
            try:
                bot_user, created = BotUser.objects.get_or_create(
                    bot=bot, 
                    telegram_id=from_user['id'],
                    defaults={
                        'username': from_user.get('username'),
                        'first_name': from_user.get('first_name'),
                        'last_name': from_user.get('last_name'),
                        'language_code': from_user.get('language_code'),
                        'last_seen_at': timezone.now(),
                    }
                )
                
                # Check if user became a member
                new_status = (my_chat_member.get('new_chat_member') or {}).get('status')
                if new_status == 'member' and not bot_user.started_at:
                    bot_user.started_at = timezone.now()
                    bot_user.save(update_fields=['started_at', 'last_seen_at'])
                    print(f"User {from_user['id']} became member, started_at set")
                elif not created:
                    bot_user.last_seen_at = timezone.now()
                    bot_user.save(update_fields=['last_seen_at'])
                    
            except Exception as e:
                print(f"Error processing my_chat_member: {e}")

    print(f"=== WEBHOOK DEBUG END ===")
    return JsonResponse({'ok': True})


@csrf_exempt
@require_http_methods(['POST'])
def set_webhook(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body.decode('utf-8') or '{}')
    bot_id = data.get('bot_id')
    webhook_url = (data.get('webhook_url') or '').strip()
    if not bot_id or not webhook_url:
        return JsonResponse({'error': 'bot_id and webhook_url required'}, status=400)
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return JsonResponse({'error': 'bot not found'}, status=404)
    r = requests.post(f"https://api.telegram.org/bot{bot.token}/setWebhook", json={
        'url': webhook_url
    }, timeout=10)
    try:
        js = r.json()
    except Exception:
        js = {'ok': False}
    return JsonResponse(js, status=200 if js.get('ok') else 400)


@csrf_exempt
def staff_send_form(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        bot_id = request.POST.get('bot_id')
        chat_id = (request.POST.get('chat_id') or '').strip()
        text = (request.POST.get('text') or '').strip()
        error = None
        ok = False
        try:
            bot = Bot.objects.get(id=bot_id)
        except Bot.DoesNotExist:
            bot = None
            error = 'Bot not found'

        if bot and chat_id and text:
            resp = requests.post(f"https://api.telegram.org/bot{bot.token}/sendMessage", json={
                'chat_id': chat_id,
                'text': text,
                'disable_web_page_preview': True,
            }, timeout=10)
            try:
                js = resp.json()
            except Exception:
                js = {'ok': False, 'description': 'Invalid response'}
            ok = bool(js.get('ok'))
            # log
            try:
                bot_user = BotUser.objects.filter(bot=bot, telegram_id=int(chat_id)).first()
            except Exception:
                bot_user = None
            
            if not bot_user:
                try:
                    bot_user = BotUser.objects.create(bot=bot, telegram_id=int(chat_id))
                except Exception:
                    bot_user = None
                    
            if bot_user:
                SendLog.objects.create(
                    campaign=None,  # optional for ad-hoc sends
                    bot_user=bot_user,
                    status=SendLog.STATUS_SENT if ok else SendLog.STATUS_FAILED,
                    message_id=str((js.get('result') or {}).get('message_id')) if ok else None,
                    error=None if ok else (js.get('description') or 'Unknown error'),
                    sent_at=timezone.now() if ok else None,
                )
        elif not error:
            error = 'All fields are required'

        if ok:
            return render(request, 'hub/send_form.html', {
                'bots': Bot.objects.all(),
                'success': True
            })
        else:
            return render(request, 'hub/send_form.html', {
                'bots': Bot.objects.all(),
                'error': error or 'Failed to send'
            })

    return render(request, 'hub/send_form.html', {'bots': Bot.objects.all()})


@csrf_exempt
@require_http_methods(['POST'])
def broadcast_all(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body.decode('utf-8') or '{}')
    bot_id = data.get('bot_id')
    bot_token = (data.get('bot_token') or '').strip()
    text = (data.get('text') or '').strip()
    
    print(f"=== BROADCAST ALL DEBUG ===")
    print(f"bot_id: {bot_id}")
    print(f"bot_token: {bot_token}")
    print(f"text: {text}")
    
    if not text:
        return JsonResponse({'error': 'text required'}, status=400)

    bot = None
    if bot_id:
        try:
            bot = Bot.objects.get(id=bot_id)
            print(f"Bot found by ID: {bot.name}")
            print(f"Bot token (last 10 chars): ...{bot.token[-10:] if bot.token else 'None'}")
        except Bot.DoesNotExist:
            print(f"Bot with ID {bot_id} not found!")
            return JsonResponse({'error': 'bot not found'}, status=404)
    elif bot_token:
        bot = Bot.objects.filter(token=bot_token).first()
        if bot:
            print(f"Bot found by token: {bot.name}")
        else:
            print(f"Bot with token not found!")
            return JsonResponse({'error': 'bot not found for token'}, status=404)
    else:
        return JsonResponse({'error': 'bot_id or bot_token required'}, status=400)

    # Test bot token first
    print("Testing bot token with Telegram API...")
    try:
        test_response = requests.get(f"https://api.telegram.org/bot{bot.token}/getMe", timeout=10)
        test_json = test_response.json()
        print(f"Bot API test: {test_json}")
        if not test_json.get('ok'):
            return JsonResponse({'error': 'Invalid bot token or bot not accessible'}, status=400)
        print(f"Bot username: @{test_json.get('result', {}).get('username', 'unknown')}")
    except Exception as e:
        print(f"Error testing bot token: {e}")
        return JsonResponse({'error': f'Error testing bot token: {str(e)}'}, status=400)

    # Get all users who have started the bot and are not blocked
    users = BotUser.objects.filter(
        bot=bot, 
        is_blocked=False, 
        started_at__isnull=False
    )
    
    total_users = users.count()
    print(f"Total users to broadcast to: {total_users}")
    
    # Debug: print all users
    for user in users:
        print(f"User: {user.telegram_id} - Started: {user.started_at} - Blocked: {user.is_blocked}")
    
    if total_users == 0:
        print("No users found! Checking all users for this bot...")
        all_users = BotUser.objects.filter(bot=bot)
        print(f"Total users in DB for bot: {all_users.count()}")
        for user in all_users:
            print(f"All Users: {user.telegram_id} - Started: {user.started_at} - Blocked: {user.is_blocked}")
    
    ok_count = 0
    fail_count = 0
    failures = []
    failures = []

    for user in users:
        try:
            print(f"Sending to user: {user.telegram_id}")
            
            # First, try to get chat info to verify user exists
            try:
                chat_response = requests.get(
                    f"https://api.telegram.org/bot{bot.token}/getChat",
                    params={'chat_id': user.telegram_id},
                    timeout=10
                )
                chat_json = chat_response.json()
                print(f"Chat info for {user.telegram_id}: {chat_json}")
                
                if not chat_json.get('ok'):
                    print(f"  - Cannot access chat {user.telegram_id}: {chat_json.get('description')}")
                    # Mark as blocked if chat not found
                    if 'not found' in chat_json.get('description', '').lower():
                        user.is_blocked = True
                        user.save(update_fields=['is_blocked'])
                        print(f"  - Marked user {user.telegram_id} as blocked (chat not found)")
                        continue
            except Exception as e:
                print(f"  - Error checking chat {user.telegram_id}: {e}")
            
            # Send the message
            response = requests.post(
                f"https://api.telegram.org/bot{bot.token}/sendMessage", 
                json={
                    'chat_id': user.telegram_id,
                    'text': text,
                    'disable_web_page_preview': True,
                }, 
                timeout=15
            )
            
            try:
                js = response.json()
                print(f"Send response for {user.telegram_id}: {js}")
            except Exception:
                js = {'ok': False, 'description': 'Invalid JSON response'}
            
            is_success = bool(js.get('ok'))
            
            if is_success:
                ok_count += 1
                print(f"✓ Sent to user {user.telegram_id}")
            else:
                fail_count += 1
                error_desc = js.get('description', 'Unknown error')
                print(f"✗ Failed to send to user {user.telegram_id}: {error_desc}")
                
                # Handle various error cases
                error_lower = error_desc.lower()
                if any(phrase in error_lower for phrase in ['blocked', 'bot was blocked', 'user is deactivated']):
                    user.is_blocked = True
                    user.save(update_fields=['is_blocked'])
                    print(f"  - Marked user {user.telegram_id} as blocked")
                elif 'chat not found' in error_lower:
                    user.is_blocked = True
                    user.save(update_fields=['is_blocked'])
                    print(f"  - Marked user {user.telegram_id} as blocked (chat not found)")
            
            # Create send log
            SendLog.objects.create(
                campaign=None,  # This is for ad-hoc broadcasts
                bot_user=user,
                status=SendLog.STATUS_SENT if is_success else SendLog.STATUS_FAILED,
                message_id=str((js.get('result') or {}).get('message_id')) if is_success else None,
                error=None if is_success else error_desc,
                sent_at=timezone.now() if is_success else None,
            )
            
        except Exception as ex:
            fail_count += 1
            error_msg = str(ex)
            print(f"✗ Exception sending to user {user.telegram_id}: {error_msg}")
            
            # Create failed send log
            SendLog.objects.create(
                campaign=None,
                bot_user=user,
                status=SendLog.STATUS_FAILED,
                error=error_msg,
            )

    print(f"Broadcast completed: {ok_count} sent, {fail_count} failed")
    print(f"=== BROADCAST ALL END ===")
    
    return JsonResponse({
        'ok': True, 
        'total_users': total_users,
        'sent': ok_count, 
        'failed': fail_count
    })


@csrf_exempt
@require_http_methods(['POST'])
def broadcast_action(request: HttpRequest) -> JsonResponse:
    """Broadcast different Telegram actions to all started users of a bot.

    Body JSON:
    - bot_id or bot_token
    - action: 'text' | 'poll' | 'photo' | 'video' | 'pin'
    - text: used for 'text' and 'pin' (message to send and pin)
    - photo: URL (for 'photo')
    - caption: optional (for 'photo' and 'video')
    - video: URL (for 'video')
    - question: poll question (for 'poll')
    - options: list[str] poll options (for 'poll')
    - is_anonymous: optional bool (for 'poll')
    - allows_multiple_answers: optional bool (for 'poll')
    """
    data = json.loads(request.body.decode('utf-8') or '{}')
    bot_id = data.get('bot_id')
    bot_token = (data.get('bot_token') or '').strip()
    action = (data.get('action') or 'text').strip()

    bot = None
    if bot_id:
        try:
            bot = Bot.objects.get(id=bot_id)
        except Bot.DoesNotExist:
            return JsonResponse({'error': 'bot not found'}, status=404)
    elif bot_token:
        bot = Bot.objects.filter(token=bot_token).first()
        if not bot:
            return JsonResponse({'error': 'bot not found for token'}, status=404)
    else:
        return JsonResponse({'error': 'bot_id or bot_token required'}, status=400)

    users = BotUser.objects.filter(
        bot=bot, is_blocked=False, started_at__isnull=False
    ).only('telegram_id')

    ok_count = 0
    fail_count = 0
    failures = []

    for u in users:
        try:
            if action == 'text':
                text = (data.get('text') or '').strip()
                if not text:
                    return JsonResponse({'error': 'text required for action=text'}, status=400)
                resp = requests.post(
                    f"https://api.telegram.org/bot{bot.token}/sendMessage",
                    json={'chat_id': u.telegram_id, 'text': text, 'disable_web_page_preview': True},
                    timeout=15,
                )
            elif action == 'photo':
                photo = (data.get('photo') or '').strip()
                photo_path = (data.get('photo_path') or '').strip()
                if not photo and not photo_path:
                    return JsonResponse({'error': 'photo or photo_path required for action=photo'}, status=400)
                caption = data.get('caption')
                if photo_path:
                    try:
                        file_obj = default_storage.open(photo_path, 'rb')
                    except Exception:
                        photo_path = ''
                    if photo_path:
                        filename = photo_path.split('/')[-1]
                        mime, _ = mimetypes.guess_type(filename)
                        files = {
                            'photo': (filename, file_obj, mime or 'application/octet-stream')
                        }
                        data_fields = {'chat_id': str(u.telegram_id)}
                        if caption:
                            data_fields['caption'] = caption
                        resp = requests.post(
                            f"https://api.telegram.org/bot{bot.token}/sendPhoto",
                            data=data_fields,
                            files=files,
                            timeout=60,
                        )
                        try:
                            file_obj.close()
                        except Exception:
                            pass
                    else:
                        payload = {'chat_id': u.telegram_id, 'photo': photo}
                        if caption:
                            payload['caption'] = caption
                        resp = requests.post(
                            f"https://api.telegram.org/bot{bot.token}/sendPhoto",
                            json=payload,
                            timeout=20,
                        )
                else:
                    payload = {'chat_id': u.telegram_id, 'photo': photo}
                    if caption:
                        payload['caption'] = caption
                    resp = requests.post(
                        f"https://api.telegram.org/bot{bot.token}/sendPhoto",
                        json=payload,
                        timeout=20,
                    )
            elif action == 'video':
                video = (data.get('video') or '').strip()
                video_path = (data.get('video_path') or '').strip()
                if not video and not video_path:
                    return JsonResponse({'error': 'video or video_path required for action=video'}, status=400)
                caption = data.get('caption')
                if video_path:
                    # Upload the actual file to Telegram
                    try:
                        file_obj = default_storage.open(video_path, 'rb')
                    except Exception:
                        # Fallback to URL if path invalid
                        video_path = ''
                    if video_path:
                        filename = video_path.split('/')[-1]
                        mime, _ = mimetypes.guess_type(filename)
                        files = {
                            'video': (filename, file_obj, mime or 'application/octet-stream')
                        }
                        data_fields = {'chat_id': str(u.telegram_id)}
                        if caption:
                            data_fields['caption'] = caption
                        resp = requests.post(
                            f"https://api.telegram.org/bot{bot.token}/sendVideo",
                            data=data_fields,
                            files=files,
                            timeout=60,
                        )
                        try:
                            file_obj.close()
                        except Exception:
                            pass
                    else:
                        payload = {'chat_id': u.telegram_id, 'video': video}
                        if caption:
                            payload['caption'] = caption
                        resp = requests.post(
                            f"https://api.telegram.org/bot{bot.token}/sendVideo",
                            json=payload,
                            timeout=30,
                        )
                else:
                    payload = {'chat_id': u.telegram_id, 'video': video}
                    if caption:
                        payload['caption'] = caption
                    resp = requests.post(
                        f"https://api.telegram.org/bot{bot.token}/sendVideo",
                        json=payload,
                        timeout=30,
                    )
            elif action == 'poll':
                question = (data.get('question') or '').strip()
                options = data.get('options') or []
                if not question or not isinstance(options, list) or len(options) < 2:
                    return JsonResponse({'error': 'poll requires question and at least 2 options'}, status=400)
                payload = {
                    'chat_id': u.telegram_id,
                    'question': question,
                    'options': options,
                }
                if 'is_anonymous' in data:
                    payload['is_anonymous'] = bool(data['is_anonymous'])
                if 'allows_multiple_answers' in data:
                    payload['allows_multiple_answers'] = bool(data['allows_multiple_answers'])
                resp = requests.post(
                    f"https://api.telegram.org/bot{bot.token}/sendPoll",
                    json=payload,
                    timeout=20,
                )
            elif action == 'pin':
                text = (data.get('text') or '').strip()
                if not text:
                    return JsonResponse({'error': 'text required for action=pin'}, status=400)
                # Send a message then pin it
                send = requests.post(
                    f"https://api.telegram.org/bot{bot.token}/sendMessage",
                    json={'chat_id': u.telegram_id, 'text': text},
                    timeout=15,
                )
                try:
                    send_js = send.json()
                except Exception:
                    send_js = {'ok': False}
                if not send_js.get('ok'):
                    resp = send
                else:
                    mid = (send_js.get('result') or {}).get('message_id')
                    resp = requests.post(
                        f"https://api.telegram.org/bot{bot.token}/pinChatMessage",
                        json={'chat_id': u.telegram_id, 'message_id': mid, 'disable_notification': True},
                        timeout=15,
                    )
            else:
                return JsonResponse({'error': f'unsupported action {action}'}, status=400)

            try:
                js = resp.json()
            except Exception:
                js = {'ok': False, 'description': 'Invalid JSON response'}

            if js.get('ok'):
                ok_count += 1
            else:
                fail_count += 1
                failures.append({
                    'chat_id': u.telegram_id,
                    'error': js.get('description') or 'Unknown error',
                    'action': action,
                })
        except Exception:
            fail_count += 1
            failures.append({'chat_id': u.telegram_id, 'error': 'Unhandled exception', 'action': action})

    return JsonResponse({'ok': True, 'action': action, 'sent': ok_count, 'failed': fail_count, 'failures': failures})


# Debug endpoint
@csrf_exempt
def debug_bot_users(request: HttpRequest, bot_id: int) -> JsonResponse:
    """Enhanced debug endpoint"""
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return JsonResponse({'error': 'bot not found'}, status=404)
    
    # Get all users for this bot
    all_users = list(BotUser.objects.filter(bot=bot).values(
        'id', 'telegram_id', 'username', 'first_name', 'last_name', 
        'is_blocked', 'started_at', 'last_seen_at', 'joined_at'
    ))
    
    # Count users by status
    total_users = BotUser.objects.filter(bot=bot).count()
    started_users = BotUser.objects.filter(bot=bot, started_at__isnull=False).count()
    blocked_users = BotUser.objects.filter(bot=bot, is_blocked=True).count()
    active_users = BotUser.objects.filter(
        bot=bot, 
        started_at__isnull=False, 
        is_blocked=False
    ).count()
    
    # Get recent webhook events
    recent_events = list(WebhookEvent.objects.filter(bot=bot).order_by('-created_at')[:10].values(
        'id', 'event_type', 'payload', 'created_at'
    ))
    
    # Get recent send logs
    recent_sends = list(SendLog.objects.filter(
        bot_user__bot=bot
    ).order_by('-created_at')[:10].values(
        'id', 'bot_user__telegram_id', 'status', 'error', 'sent_at', 'created_at'
    ))
    
    return JsonResponse({
        'bot_name': bot.name,
        'bot_active': bot.is_active,
        'bot_token_last_4': bot.token[-4:] if bot.token else 'None',
        'stats': {
            'total_users': total_users,
            'started_users': started_users,
            'blocked_users': blocked_users,
            'active_users': active_users,
        },
        'users': all_users,
        'recent_webhook_events': recent_events,
        'recent_send_logs': recent_sends
    })


# Test webhook endpoint
@csrf_exempt 
def test_webhook(request: HttpRequest, bot_id: int) -> JsonResponse:
    """Test webhook with a simulated /start message"""
    test_payload = {
        "update_id": 999999,
        "message": {
            "message_id": 999,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "username": "testuser",
                "language_code": "en"
            },
            "chat": {
                "id": 123456789,
                "first_name": "Test",
                "last_name": "User", 
                "username": "testuser",
                "type": "private"
            },
            "date": 1640995200,
            "text": "/start"
        }
    }
    
    print("=== TEST WEBHOOK CALLED ===")
    
    # Simulate the webhook call
    request._body = json.dumps(test_payload).encode('utf-8')
    return telegram_webhook(request, bot_id)


# Manual user creation endpoint for testing
@csrf_exempt
@require_http_methods(['POST'])
def create_test_user(request: HttpRequest, bot_id: int) -> JsonResponse:
    """Manually create a test user for debugging"""
    try:
        bot = Bot.objects.get(id=bot_id)
    except Bot.DoesNotExist:
        return JsonResponse({'error': 'bot not found'}, status=404)
    
    data = json.loads(request.body.decode('utf-8') or '{}')
    telegram_id = data.get('telegram_id', 123456789)
    
    try:
        bot_user, created = BotUser.objects.get_or_create(
            bot=bot,
            telegram_id=telegram_id,
            defaults={
                'username': 'testuser',
                'first_name': 'Test',
                'last_name': 'User',
                'started_at': timezone.now(),
                'last_seen_at': timezone.now(),
            }
        )
        
        if not created and not bot_user.started_at:
            bot_user.started_at = timezone.now()
            bot_user.save(update_fields=['started_at'])
        
        return JsonResponse({
            'ok': True,
            'created': created,
            'user': {
                'id': bot_user.id,
                'telegram_id': bot_user.telegram_id,
                'username': bot_user.username,
                'started_at': bot_user.started_at,
                'is_blocked': bot_user.is_blocked,
            }
        })
        
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


@csrf_exempt
@require_http_methods(['POST'])
def import_updates(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body.decode('utf-8') or '{}')
    bot_token = (data.get('bot_token') or '').strip()
    if not bot_token:
        return JsonResponse({'error': 'bot_token required'}, status=400)

    bot = Bot.objects.filter(token=bot_token).first()
    if not bot:
        bot = Bot.objects.create(name='Imported Bot', token=bot_token, is_active=True)

    try:
        r = requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", timeout=15)
        js = r.json()
    except Exception as ex:
        return JsonResponse({'error': f'failed to fetch updates: {ex}'}, status=400)

    if not js.get('ok'):
        return JsonResponse(js, status=400)

    upserted = 0
    started = 0
    for upd in js.get('result', []):
        msg = upd.get('message') or upd.get('edited_message') or {}
        if not msg:
            continue
        from_user = msg.get('from') or {}
        chat = msg.get('chat') or {}
        chat_id = chat.get('id') or from_user.get('id')
        if not chat_id:
            continue
        bu, created = BotUser.objects.get_or_create(
            bot=bot,
            telegram_id=chat_id,
            defaults={
                'username': from_user.get('username'),
                'first_name': from_user.get('first_name'),
                'last_name': from_user.get('last_name'),
                'language_code': from_user.get('language_code'),
                'last_seen_at': timezone.now(),
            }
        )
        if created:
            upserted += 1
        else:
            changed = False
            for field, value in {
                'username': from_user.get('username'),
                'first_name': from_user.get('first_name'),
                'last_name': from_user.get('last_name'),
                'language_code': from_user.get('language_code'),
            }.items():
                if value and getattr(bu, field) != value:
                    setattr(bu, field, value)
                    changed = True
            bu.last_seen_at = timezone.now()
            if changed:
                bu.save()
        text = (msg.get('text') or '').strip()
        if text.startswith('/start') and not bu.started_at:
            bu.started_at = timezone.now()
            bu.save(update_fields=['started_at'])
            started += 1

    return JsonResponse({'ok': True, 'upserted': upserted, 'started_marked': started})