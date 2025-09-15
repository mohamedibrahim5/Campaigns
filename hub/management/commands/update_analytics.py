"""
Management command to update campaign analytics
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from hub.models import Candidate, CampaignAnalytics


class Command(BaseCommand):
    help = 'Update campaign analytics for all candidates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--candidate-id',
            type=str,
            help='Update analytics only for specific candidate ID',
        )

    def handle(self, *args, **options):
        self.stdout.write('Updating campaign analytics...')
        
        candidates = Candidate.objects.filter(is_active=True)
        if options['candidate_id']:
            candidates = candidates.filter(id=options['candidate_id'])
        
        for candidate in candidates:
            self.update_candidate_analytics(candidate)
        
        self.stdout.write(
            self.style.SUCCESS('Campaign analytics updated successfully')
        )

    def update_candidate_analytics(self, candidate):
        """Update analytics for a specific candidate"""
        self.stdout.write(f'Updating analytics for {candidate.name}...')
        
        # Get or create analytics record
        analytics, created = CampaignAnalytics.objects.get_or_create(
            candidate=candidate
        )
        
        # Update counts
        analytics.total_supporters = candidate.supporters.count()
        analytics.total_volunteers = candidate.volunteers.filter(is_active=True).count()
        analytics.total_events = candidate.events.count()
        analytics.total_polls = candidate.polls.count()
        analytics.total_speeches = candidate.speeches.count()
        analytics.total_fake_news_alerts = candidate.fake_news_alerts.count()
        analytics.last_updated = timezone.now()
        
        analytics.save()
        
        self.stdout.write(
            f'  Supporters: {analytics.total_supporters}, '
            f'Volunteers: {analytics.total_volunteers}, '
            f'Events: {analytics.total_events}, '
            f'Polls: {analytics.total_polls}, '
            f'Speeches: {analytics.total_speeches}, '
            f'Fake News Alerts: {analytics.total_fake_news_alerts}'
        )
