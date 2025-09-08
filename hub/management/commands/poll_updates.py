import json
import time
import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from hub.models import Bot, BotUser, MessageLog


class Command(BaseCommand):
    help = "Long-poll Telegram getUpdates for a bot token and persist users/messages"

    def add_arguments(self, parser):
        parser.add_argument('--bot-token', required=False, help='Telegram bot token')
        parser.add_argument('--bot-id', type=int, required=False, help='Bot ID from DB')
        parser.add_argument('--timeout', type=int, default=50, help='Long poll timeout seconds')
        parser.add_argument('--sleep', type=int, default=1, help='Sleep between polls when no updates')

    def handle(self, *args, **options):
        bot_token = options.get('bot_token')
        bot_id = options.get('bot_id')
        timeout = options.get('timeout')
        sleep_sec = options.get('sleep')

        if not bot_token and not bot_id:
            raise CommandError('Provide --bot-token or --bot-id')

        bot = None
        if bot_id:
            try:
                bot = Bot.objects.get(id=bot_id)
                bot_token = bot.token
            except Bot.DoesNotExist:
                raise CommandError('Bot not found for --bot-id')
        elif bot_token:
            bot = Bot.objects.filter(token=bot_token).first()
            if not bot:
                bot = Bot.objects.create(name='Polled Bot', token=bot_token, is_active=True)

        self.stdout.write(self.style.SUCCESS(f"Polling updates for bot: {bot.name}"))

        offset = None
        while True:
            try:
                params = {'timeout': timeout}
                if offset:
                    params['offset'] = offset
                r = requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", params=params, timeout=timeout+5)
                js = r.json()
            except Exception as ex:
                self.stderr.write(f"Error fetching updates: {ex}")
                time.sleep(sleep_sec)
                continue

            if not js.get('ok'):
                self.stderr.write(f"Telegram returned error: {js}")
                time.sleep(sleep_sec)
                continue

            for upd in js.get('result', []):
                offset = upd['update_id'] + 1

                # Handle callback queries first (button presses)
                callback_query = upd.get('callback_query')
                if callback_query:
                    cq_from = callback_query.get('from') or {}
                    cq_message = callback_query.get('message') or {}
                    cq_chat = (cq_message.get('chat') or {})
                    cq_chat_id = cq_chat.get('id') or cq_from.get('id')
                    data = callback_query.get('data') or ''

                    if not cq_chat_id:
                        continue

                    bot_user, _ = BotUser.objects.get_or_create(
                        bot=bot,
                        telegram_id=cq_chat_id,
                        defaults={
                            'username': cq_from.get('username'),
                            'first_name': cq_from.get('first_name'),
                            'last_name': cq_from.get('last_name'),
                            'language_code': cq_from.get('language_code'),
                            'last_seen_at': timezone.now(),
                        }
                    )

                    bot_user.last_seen_at = timezone.now()
                    bot_user.save(update_fields=['last_seen_at'])

                    # Acknowledge callback to avoid loading state on client
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                            json={
                                'callback_query_id': callback_query.get('id'),
                                'text': 'Ready! You can send your question now.',
                                'show_alert': False,
                            },
                            timeout=10,
                        )
                    except Exception as ex:
                        self.stderr.write(f"Error answering callback: {ex}")

                    if data == 'enable_questions':
                        bot_user.state = 'enabled'
                        if not bot_user.started_at:
                            bot_user.started_at = timezone.now()
                        bot_user.save(update_fields=['state', 'started_at'] if bot_user.started_at else ['state'])

                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                                json={
                                    'chat_id': cq_chat_id,
                                    'text': 'You can now send your question about campaigns/candidates.',
                                },
                                timeout=10,
                            )
                        except Exception as ex:
                            self.stderr.write(f"Error sending enabled message: {ex}")

                    # Continue to next update after handling callback
                    continue

                # Handle standard messages
                msg = upd.get('message') or upd.get('edited_message') or {}
                if not msg:
                    continue

                chat = msg.get('chat') or {}
                from_user = msg.get('from') or {}
                chat_id = chat.get('id') or from_user.get('id')
                if not chat_id:
                    continue

                bot_user, created = BotUser.objects.get_or_create(
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
                if not created:
                    bot_user.last_seen_at = timezone.now()
                    bot_user.save(update_fields=['last_seen_at'])

                text = (msg.get('text') or '').strip()

                # On /start: send pinned intro with button, set awaiting state
                if text.startswith('/start'):
                    if not bot_user.started_at:
                        bot_user.started_at = timezone.now()
                    bot_user.state = 'await_button'
                    bot_user.save(update_fields=['started_at', 'state'] if bot_user.started_at else ['state'])

                    intro_text = (
                        "Welcome! Press the button below to start asking about campaigns/candidates."
                    )
                    try:
                        send_resp = requests.post(
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            json={
                                'chat_id': chat_id,
                                'text': intro_text,
                                'reply_markup': {
                                    'inline_keyboard': [[
                                        {
                                            'text': 'Ask a question',
                                            'callback_data': 'enable_questions'
                                        }
                                    ]]
                                },
                            },
                            timeout=10,
                        )
                        send_js = send_resp.json()
                        message_to_pin_id = None
                        if send_js.get('ok') and send_js.get('result'):
                            message_to_pin_id = send_js['result'].get('message_id')
                        if message_to_pin_id:
                            try:
                                requests.post(
                                    f"https://api.telegram.org/bot{bot_token}/pinChatMessage",
                                    json={
                                        'chat_id': chat_id,
                                        'message_id': message_to_pin_id,
                                        'disable_notification': True,
                                    },
                                    timeout=10,
                                )
                            except Exception as ex:
                                self.stderr.write(f"Error pinning message: {ex}")
                    except Exception as ex:
                        self.stderr.write(f"Error sending intro/button: {ex}")

                else:
                    # Gate messages until enabled
                    if bot_user.state != 'enabled':
                        # Delete the incoming message to simulate blocking send
                        try:
                            incoming_message_id = msg.get('message_id')
                            if incoming_message_id is not None:
                                requests.post(
                                    f"https://api.telegram.org/bot{bot_token}/deleteMessage",
                                    json={
                                        'chat_id': chat_id,
                                        'message_id': incoming_message_id,
                                    },
                                    timeout=10,
                                )
                        except Exception as ex:
                            self.stderr.write(f"Error deleting gated message: {ex}")

                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                                json={
                                    'chat_id': chat_id,
                                    'text': 'Thanks! Press the button to ask another question.',
                                    'reply_markup': {
                                        'inline_keyboard': [[
                                            {
                                                'text': 'Ask another question',
                                                'callback_data': 'enable_questions'
                                            }
                                        ]]
                                    },
                                },
                                timeout=10,
                            )
                        except Exception as ex:
                            self.stderr.write(f"Error sending gate prompt: {ex}")
                        continue

                # Persist all messages
                MessageLog.objects.create(
                    bot=bot,
                    bot_user=bot_user,
                    message_id=str(msg.get('message_id')) if msg.get('message_id') is not None else None,
                    chat_id=chat_id,
                    from_user_id=from_user.get('id'),
                    text=text or None,
                    raw=msg,
                )

                # After accepting one question, close chat again until button is pressed
                if bot_user.state == 'enabled' and not text.startswith('/start'):
                    bot_user.state = 'await_button'
                    bot_user.save(update_fields=['state'])
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            json={
                                'chat_id': chat_id,
                                'text': 'Thanks! Press the button to ask another question.',
                                'reply_markup': {
                                    'inline_keyboard': [[
                                        {
                                            'text': 'Ask another question',
                                            'callback_data': 'enable_questions'
                                        }
                                    ]]
                                },
                            },
                            timeout=10,
                        )
                    except Exception as ex:
                        self.stderr.write(f"Error sending relock prompt: {ex}")

            if not js.get('result'):
                time.sleep(sleep_sec)


