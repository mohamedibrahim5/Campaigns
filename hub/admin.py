from django.contrib import admin
from .models import Bot, BotUser, Campaign, CampaignMessage, CampaignAssignment, SendLog, WebhookEvent, MessageLog


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "token")


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ("bot", "telegram_id", "username", "language_code", "is_blocked", "joined_at")
    list_filter = ("bot", "is_blocked", "language_code")
    search_fields = ("telegram_id", "username", "first_name", "last_name")


class CampaignMessageInline(admin.TabularInline):
    model = CampaignMessage
    extra = 0


class CampaignAssignmentInline(admin.TabularInline):
    model = CampaignAssignment
    extra = 0


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "campaign_type", "status", "scheduled_at", "created_at")
    list_filter = ("campaign_type", "status")
    search_fields = ("name",)
    inlines = [CampaignMessageInline, CampaignAssignmentInline]


@admin.register(SendLog)
class SendLogAdmin(admin.ModelAdmin):
    list_display = ("campaign", "bot_user", "status", "sent_at", "created_at")
    list_filter = ("status", "campaign")
    search_fields = ("message_id", "error")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("bot", "event_type", "created_at")
    list_filter = ("event_type", "bot")
    search_fields = ("event_type",)


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("bot", "chat_id", "from_user_id", "message_id", "received_at")
    list_filter = ("bot",)
    search_fields = ("chat_id", "from_user_id", "text")

