from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Bot(models.Model):
    name = models.CharField(max_length=150)
    token = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    admin_chat_id = models.BigIntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    bot_link = models.URLField(blank=True, null=True, help_text="Direct link to the Telegram bot (e.g., https://t.me/your_bot)")

    def __str__(self) -> str:
        return f"{self.name}"


class BotUser(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="users")
    telegram_id = models.BigIntegerField()
    username = models.CharField(max_length=150, blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    language_code = models.CharField(max_length=10, blank=True, null=True)
    is_blocked = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        unique_together = ("bot", "telegram_id")

    def __str__(self) -> str:
        return f"{self.username or self.telegram_id} ({self.bot.name})"


class Campaign(models.Model):
    TYPE_BROADCAST = "broadcast"
    TYPE_SCHEDULED = "scheduled"
    TYPE_TRIGGERED = "triggered"
    TYPE_CHOICES = (
        (TYPE_BROADCAST, "Broadcast"),
        (TYPE_SCHEDULED, "Scheduled"),
        (TYPE_TRIGGERED, "Triggered"),
    )

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_COMPLETED, "Completed"),
    )

    name = models.CharField(max_length=200)
    campaign_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_BROADCAST)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name}"


class CampaignAssignment(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="assignments")
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="campaign_assignments")

    class Meta:
        unique_together = ("campaign", "bot")

    def __str__(self) -> str:
        return f"{self.campaign.name} -> {self.bot.name}"


class CampaignMessage(models.Model):
    CONTENT_TEXT = "text"
    CONTENT_IMAGE = "image"
    CONTENT_DOCUMENT = "document"
    CONTENT_CHOICES = (
        (CONTENT_TEXT, "Text"),
        (CONTENT_IMAGE, "Image"),
        (CONTENT_DOCUMENT, "Document"),
    )

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="messages")
    order_index = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=20, choices=CONTENT_CHOICES, default=CONTENT_TEXT)
    text = models.TextField(blank=True, null=True)
    media_url = models.URLField(blank=True, null=True)
    extra = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ["order_index", "id"]

    def __str__(self) -> str:
        return f"{self.campaign.name} message #{self.order_index}"


class SendLog(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    )

    # FIXED: Made campaign optional for ad-hoc sends
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="send_logs", null=True, blank=True)
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE, related_name="send_logs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    message_id = models.CharField(max_length=100, blank=True, null=True)
    error = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        campaign_name = self.campaign.name if self.campaign else "Ad-hoc"
        return f"{campaign_name} -> {self.bot_user} [{self.status}]"

class WebhookEvent(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="webhook_events")
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.bot.name} {self.event_type}"


class MessageLog(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="message_logs")
    bot_user = models.ForeignKey(BotUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="message_logs")
    message_id = models.CharField(max_length=64, blank=True, null=True)
    chat_id = models.BigIntegerField()
    from_user_id = models.BigIntegerField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    raw = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["bot", "chat_id"]),
            models.Index(fields=["bot", "received_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.bot.name} chat={self.chat_id} msg={self.message_id or '-'}"


# ===== ELECTION 360 SAAS MODELS =====

class Candidate(models.Model):
    """Candidate profile with CV, program, and media"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    # Public-friendly display name used in pretty URLs (can include Arabic and spaces)
    public_url_name = models.CharField(max_length=300, blank=True, null=True, unique=True)
    position = models.CharField(max_length=200)  # e.g., "Mayor of Cairo", "President"
    party = models.CharField(max_length=200, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)  # CV content
    program = models.TextField(blank=True, null=True)  # Election program
    profile_image = models.ImageField(upload_to='candidates/', blank=True, null=True)
    logo = models.ImageField(upload_to='candidates/logos/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    social_media = models.JSONField(default=dict, blank=True)  # {facebook: url, twitter: url, etc}
    bot = models.ForeignKey(Bot, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.position}"


class CandidateUser(models.Model):
    """User account for candidates to access their dashboard"""
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='candidate_profile')
    candidate = models.OneToOneField(Candidate, on_delete=models.CASCADE, related_name='dashboard_user')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Candidate User'
        verbose_name_plural = 'Candidate Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.candidate.name}"
    
    @property
    def username(self):
        return self.user.username
    
    @property
    def email(self):
        return self.user.email
    
    @property
    def is_active(self):
        return self.user.is_active


class Gallery(models.Model):
    """Gallery for candidate images and videos"""
    MEDIA_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('external', 'External Link'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='gallery_items')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    file = models.FileField(upload_to='candidates/gallery/', blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to='candidates/gallery/thumbnails/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-created_at']
        verbose_name_plural = 'Gallery Items'

    def __str__(self):
        return f"{self.candidate.name} - {self.title} ({self.media_type})"

    @property
    def file_url(self):
        if self.file:
            return self.file.url
        return None

    @property
    def thumbnail_url(self):
        if self.thumbnail:
            return self.thumbnail.url
        return None

    @property
    def is_youtube(self):
        if self.media_type != 'external' or not self.external_url:
            return False
        url = (self.external_url or '').lower()
        return 'youtube.com/watch' in url or 'youtu.be/' in url

    @property
    def youtube_embed_id(self):
        if not self.is_youtube:
            return None
        try:
            from urllib.parse import urlparse, parse_qs
            u = urlparse(self.external_url)
            if 'youtu.be' in u.netloc:
                return u.path.strip('/')
            if 'youtube.com' in u.netloc:
                q = parse_qs(u.query)
                return (q.get('v') or [None])[0]
        except Exception:
            return None
        return None


class Event(models.Model):
    """Events and announcements for candidates"""
    EVENT_TYPES = [
        ('conference', 'Conference'),
        ('meeting', 'Meeting'),
        ('rally', 'Rally'),
        ('debate', 'Debate'),
        ('announcement', 'Announcement'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=300)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='meeting')
    location = models.CharField(max_length=300)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(blank=True, null=True)
    is_public = models.BooleanField(default=True)
    max_attendees = models.PositiveIntegerField(blank=True, null=True)
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_datetime']

    def __str__(self):
        return f"{self.title} - {self.candidate.name}"


class EventAttendance(models.Model):
    """Track who attended events"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendances')
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE, related_name='event_attendances')
    attended_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ['event', 'bot_user']

    def __str__(self):
        return f"{self.bot_user} attended {self.event.title}"


class Speech(models.Model):
    """AI-generated speeches and summaries"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='speeches')
    title = models.CharField(max_length=300)
    ideas = models.TextField()  # Input ideas from candidate
    full_speech = models.TextField()  # AI-generated full speech
    summary = models.TextField()  # Auto-generated summary for social media
    facebook_post = models.TextField(blank=True, null=True)  # Formatted for Facebook
    twitter_post = models.TextField(blank=True, null=True)  # Formatted for Twitter
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, related_name='speeches')
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.candidate.name}"


class Poll(models.Model):
    """Polls and surveys for voters"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='polls')
    title = models.CharField(max_length=300)
    question = models.TextField()
    options = models.JSONField()  # List of poll options
    is_anonymous = models.BooleanField(default=True)
    allows_multiple_answers = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.candidate.name}"


class PollResponse(models.Model):
    """Individual poll responses"""
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='responses')
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE, related_name='poll_responses')
    selected_options = models.JSONField()  # List of selected option indices
    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['poll', 'bot_user']

    def __str__(self):
        return f"{self.bot_user} responded to {self.poll.title}"


class Supporter(models.Model):
    """Voter supporters with location data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='supporters')
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE, related_name='support_records')
    city = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    support_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )  # 1-5 scale
    notes = models.TextField(blank=True, null=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['candidate', 'bot_user']
        ordering = ['-registered_at']

    def get_support_level_display(self):
        """Get Arabic display name for support level"""
        support_level_map = {
            1: 'مؤيد',
            2: 'متطوع', 
            3: 'دعم مالي',
            4: 'داعم نشط',
            5: 'داعم متميز'
        }
        return support_level_map.get(self.support_level, f'مستوى {self.support_level}')

    def __str__(self):
        return f"{self.bot_user} supports {self.candidate.name}"


class Volunteer(models.Model):
    """Volunteer management with gamification"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='volunteers')
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE, related_name='volunteer_records')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=100, default='volunteer')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['candidate', 'bot_user']
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.name} - {self.candidate.name}"


class VolunteerActivity(models.Model):
    """Track volunteer activities for gamification"""
    ACTIVITY_TYPES = [
        ('canvassing', 'Canvassing'),
        ('posters', 'Poster Distribution'),
        ('social_media', 'Social Media Sharing'),
        ('event_organization', 'Event Organization'),
        ('phone_calls', 'Phone Calls'),
        ('data_entry', 'Data Entry'),
        ('other', 'Other'),
    ]

    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    supporters_contacted = models.PositiveIntegerField(default=0)
    posters_distributed = models.PositiveIntegerField(default=0)
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    points_earned = models.PositiveIntegerField(default=0)
    location = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.volunteer.name} - {self.get_activity_type_display()}"


class FakeNewsAlert(models.Model):
    """Fake news monitoring and alerts"""
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='fake_news_alerts')
    title = models.CharField(max_length=300)
    content = models.TextField()
    source_url = models.URLField()
    source_platform = models.CharField(max_length=100)  # facebook, twitter, news_site, etc
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='medium')
    is_verified = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    response_action = models.TextField(blank=True, null=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-detected_at']

    def __str__(self):
        return f"Alert: {self.title} - {self.candidate.name}"


class DailyQuestion(models.Model):
    """Daily Q&A questions from bot users"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='daily_questions')
    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE, related_name='questions_asked')
    question = models.TextField()
    answer = models.TextField(blank=True, null=True)
    is_answered = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    asked_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-asked_at']

    def __str__(self):
        return f"Q: {self.question[:50]}... - {self.candidate.name}"


class CampaignAnalytics(models.Model):
    """Analytics and metrics for campaigns"""
    candidate = models.OneToOneField(Candidate, on_delete=models.CASCADE, related_name='analytics')
    total_supporters = models.PositiveIntegerField(default=0)
    total_volunteers = models.PositiveIntegerField(default=0)
    total_events = models.PositiveIntegerField(default=0)
    total_polls = models.PositiveIntegerField(default=0)
    total_speeches = models.PositiveIntegerField(default=0)
    total_fake_news_alerts = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Analytics for {self.candidate.name}"

