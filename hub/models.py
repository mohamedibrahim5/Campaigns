from django.db import models
from django.contrib.auth import get_user_model


class Bot(models.Model):
    name = models.CharField(max_length=150)
    token = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    admin_chat_id = models.BigIntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)

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

