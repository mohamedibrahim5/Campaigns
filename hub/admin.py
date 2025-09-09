from django.contrib import admin
from django import forms
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from .models import Bot, BotUser, Campaign, CampaignMessage, CampaignAssignment, SendLog, WebhookEvent, MessageLog


class BotAdminForm(forms.ModelForm):
    image_upload = forms.ImageField(required=False, help_text="Upload to set image_url automatically")

    class Meta:
        model = Bot
        fields = ["name", "token", "is_active", "admin_chat_id", "description", "image_url", "image_upload"]

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded = self.cleaned_data.get("image_upload")
        if uploaded:
            path = default_storage.save(
                f"uploads/{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.name}",
                ContentFile(uploaded.read())
            )
            try:
                url = default_storage.url(path)
            except Exception:
                # Fallback to MEDIA_URL
                if path.startswith('uploads/'):
                    url = settings.MEDIA_URL + path.split('uploads/')[-1]
                else:
                    url = settings.MEDIA_URL + path
            instance.image_url = url
        if commit:
            instance.save()
        return instance


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    form = BotAdminForm
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "token")


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ("bot", "telegram_id", "username", "phone_number", "language_code", "is_blocked", "joined_at")
    list_filter = ("bot", "is_blocked", "language_code")
    search_fields = ("telegram_id", "username", "first_name", "last_name", "phone_number")


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

