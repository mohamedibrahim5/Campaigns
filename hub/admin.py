from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django import forms
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from .models import (
    Bot, BotUser, Campaign, CampaignMessage, CampaignAssignment, SendLog, WebhookEvent, MessageLog,
    # Election 360 models
    Candidate, CandidateUser, Event, EventAttendance, Speech, Poll, PollResponse, Supporter, 
    Volunteer, VolunteerActivity, FakeNewsAlert, DailyQuestion, CampaignAnalytics, Gallery, Testimonial
)


class BotAdminForm(forms.ModelForm):
    image_upload = forms.ImageField(required=False, help_text="Upload to set image_url automatically")

    class Meta:
        model = Bot
        fields = ["name", "token", "is_active", "admin_chat_id", "description", "image_url", "bot_link", "image_upload"]

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


# ===== ELECTION 360 ADMIN =====

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['name', 'public_url_name', 'position', 'party', 'is_active', 'created_at']
    list_filter = ['is_active', 'party', 'created_at']
    search_fields = ['name', 'public_url_name', 'position', 'party']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'public_url_name', 'position', 'party', 'bio', 'program')
        }),
        ('Contact & Media', {
            'fields': ('profile_image', 'logo', 'website', 'email', 'phone', 'social_media', 'bot')
        }),
        ('Status', {
            'fields': ('is_active', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class EventAttendanceInline(admin.TabularInline):
    model = EventAttendance
    extra = 0
    readonly_fields = ['attended_at']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'candidate', 'event_type', 'start_datetime', 'location', 'is_public']
    list_filter = ['event_type', 'is_public', 'start_datetime', 'candidate']
    search_fields = ['title', 'description', 'location']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [EventAttendanceInline]
    date_hierarchy = 'start_datetime'


@admin.register(Speech)
class SpeechAdmin(admin.ModelAdmin):
    list_display = ['title', 'candidate', 'is_published', 'created_at']
    list_filter = ['is_published', 'candidate', 'created_at']
    search_fields = ['title', 'ideas', 'full_speech']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('candidate', 'title', 'event')
        }),
        ('Content', {
            'fields': ('ideas', 'full_speech', 'summary')
        }),
        ('Social Media', {
            'fields': ('facebook_post', 'twitter_post'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_published',)
        }),
        ('Timestamps', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class PollResponseInline(admin.TabularInline):
    model = PollResponse
    extra = 0
    readonly_fields = ['responded_at']


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ['title', 'candidate', 'is_active', 'expires_at', 'created_at']
    list_filter = ['is_active', 'is_anonymous', 'allows_multiple_answers', 'candidate']
    search_fields = ['title', 'question']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [PollResponseInline]


@admin.register(Supporter)
class SupporterAdmin(admin.ModelAdmin):
    list_display = ['bot_user', 'candidate', 'city', 'support_level', 'registered_at']
    list_filter = ['support_level', 'city', 'candidate', 'registered_at']
    search_fields = ['bot_user__first_name', 'bot_user__last_name', 'city', 'district']
    readonly_fields = ['id', 'registered_at', 'updated_at']


class VolunteerActivityInline(admin.TabularInline):
    model = VolunteerActivity
    extra = 0
    readonly_fields = ['created_at']


@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = ['name', 'candidate', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'candidate', 'joined_at']
    search_fields = ['name', 'phone', 'email']
    readonly_fields = ['id', 'joined_at', 'last_activity']
    inlines = [VolunteerActivityInline]


@admin.register(FakeNewsAlert)
class FakeNewsAlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'candidate', 'severity', 'is_verified', 'is_resolved', 'detected_at']
    list_filter = ['severity', 'is_verified', 'is_resolved', 'source_platform', 'candidate']
    search_fields = ['title', 'content', 'source_url']
    readonly_fields = ['id', 'detected_at', 'resolved_at']
    date_hierarchy = 'detected_at'


@admin.register(DailyQuestion)
class DailyQuestionAdmin(admin.ModelAdmin):
    list_display = ['question', 'candidate', 'bot_user', 'is_answered', 'asked_at']
    list_filter = ['is_answered', 'is_public', 'candidate', 'asked_at']
    search_fields = ['question', 'answer']
    readonly_fields = ['id', 'asked_at', 'answered_at']
    date_hierarchy = 'asked_at'


@admin.register(CampaignAnalytics)
class CampaignAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'total_supporters', 'total_volunteers', 'total_events', 'last_updated']
    readonly_fields = ['last_updated']

@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'title', 'media_type', 'is_featured', 'is_public', 'created_at']
    list_filter = ['media_type', 'is_featured', 'is_public', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['name', 'candidate', 'is_public', 'display_order', 'created_at']
    list_filter = ['is_public', 'candidate']
    search_fields = ['name', 'role', 'quote']
    readonly_fields = ['id', 'created_at', 'updated_at']


class CandidateUserInline(admin.StackedInline):
    model = CandidateUser
    can_delete = False
    verbose_name_plural = 'Candidate Profile'
    extra = 0
    fields = ('candidate', 'phone_number')
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['candidate'].help_text = 'Select the candidate this user will manage'
        formset.form.base_fields['phone_number'].help_text = 'Optional: Candidate phone number'
        return formset


class CandidateUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'candidate', 'phone_number', 'is_active', 'created_at']
    list_filter = ['created_at', 'candidate__position']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'candidate__name']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('user', 'candidate')}),
        ('Additional Info', {'fields': ('phone_number',)}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['user'].help_text = 'Select the Django User account for this candidate'
        form.base_fields['candidate'].help_text = 'Select the candidate this user will manage'
        form.base_fields['phone_number'].help_text = 'Optional: Candidate phone number'
        return form
    
    readonly_fields = ['created_at', 'updated_at']
    
    def is_active(self, obj):
        return obj.user.is_active
    is_active.boolean = True
    is_active.short_description = 'Active'


# Extend the default User admin to include CandidateUser inline
class CustomUserAdmin(UserAdmin):
    inlines = (CandidateUserInline,)
    list_display = UserAdmin.list_display + ('is_candidate',)
    
    def is_candidate(self, obj):
        return hasattr(obj, 'candidate_profile')
    is_candidate.boolean = True
    is_candidate.short_description = 'Is Candidate'


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(CandidateUser, CandidateUserAdmin)

