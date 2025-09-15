"""
Management command to create sample data for Election 360 SaaS
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from hub.models import (
    Candidate, Event, Speech, Poll, Supporter, Volunteer, 
    VolunteerActivity, FakeNewsAlert, DailyQuestion, CampaignAnalytics,
    Bot, BotUser
)
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample data for Election 360 SaaS testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data for Election 360 SaaS...')
        
        # Create superuser if doesn't exist
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@election360.com',
                password='admin123'
            )
            self.stdout.write('Created superuser: admin/admin123')
        
        # Create sample bot
        bot, created = Bot.objects.get_or_create(
            name='Election Bot',
            token='123456789:ABCdefGHIjklMNOpqrsTUVwxyz',
            defaults={
                'is_active': True,
                'description': 'Bot for Election 360 SaaS testing',
                'admin_chat_id': 123456789
            }
        )
        if created:
            self.stdout.write('Created sample bot')
        
        # Create sample candidate
        candidate, created = Candidate.objects.get_or_create(
            name='أحمد محمد علي',
            position='عمدة القاهرة',
            defaults={
                'party': 'حزب المستقبل',
                'bio': 'خبرة 15 سنة في الإدارة المحلية والتنمية الحضرية. حاصل على درجة الماجستير في الإدارة العامة من جامعة القاهرة.',
                'program': '''
                برنامج شامل لتطوير القاهرة:
                1. تطوير البنية التحتية والنقل العام
                2. تحسين الخدمات الصحية والتعليمية
                3. دعم المشاريع الصغيرة والمتوسطة
                4. تطوير المناطق العشوائية
                5. تعزيز السياحة والتراث
                ''',
                'email': 'ahmed@cairo-mayor.com',
                'phone': '+201234567890',
                'website': 'https://ahmed-mayor.com',
                'social_media': {
                    'facebook': 'https://facebook.com/ahmed-mayor',
                    'twitter': 'https://twitter.com/ahmed_mayor',
                    'instagram': 'https://instagram.com/ahmed_mayor'
                },
                'is_active': True
            }
        )
        if created:
            self.stdout.write('Created sample candidate: أحمد محمد علي')
        
        # Create sample events
        events_data = [
            {
                'title': 'مؤتمر انتخابي في المعادي',
                'description': 'لقاء مع الناخبين لمناقشة البرنامج الانتخابي وتطوير المعادي',
                'event_type': 'conference',
                'location': 'قاعة المعادي للمؤتمرات',
                'latitude': 29.9600,
                'longitude': 31.2600,
                'start_datetime': timezone.now() + timedelta(days=7),
                'end_datetime': timezone.now() + timedelta(days=7, hours=3),
            },
            {
                'title': 'لقاء مع شباب القاهرة',
                'description': 'حوار مفتوح مع الشباب حول مستقبل القاهرة',
                'event_type': 'meeting',
                'location': 'مركز شباب الزمالك',
                'latitude': 30.0626,
                'longitude': 31.2197,
                'start_datetime': timezone.now() + timedelta(days=14),
                'end_datetime': timezone.now() + timedelta(days=14, hours=2),
            },
            {
                'title': 'مؤتمر صحفي للإعلان عن البرنامج',
                'description': 'إعلان رسمي عن البرنامج الانتخابي الشامل',
                'event_type': 'announcement',
                'location': 'فندق النيل ريتز كارلتون',
                'latitude': 30.0444,
                'longitude': 31.2357,
                'start_datetime': timezone.now() + timedelta(days=3),
                'end_datetime': timezone.now() + timedelta(days=3, hours=1),
            }
        ]
        
        for event_data in events_data:
            event, created = Event.objects.get_or_create(
                candidate=candidate,
                title=event_data['title'],
                defaults=event_data
            )
            if created:
                self.stdout.write(f'Created event: {event.title}')
        
        # Create sample speech
        speech, created = Speech.objects.get_or_create(
            candidate=candidate,
            title='خطاب الترشح الرسمي',
            defaults={
                'ideas': 'أريد التحدث عن التطوير والاستثمار في البنية التحتية، وتحسين الخدمات العامة، ودعم الشباب والمرأة',
                'full_speech': '''
                السيدات والسادة، أتقدم لكم اليوم كمرشح لمنصب عمدة القاهرة العظيمة.
                
                القاهرة ليست مجرد مدينة، بل هي قلب مصر النابض، وعاصمة الحضارة العربية والإسلامية.
                
                برنامجي يركز على:
                1. تطوير البنية التحتية والنقل العام
                2. تحسين الخدمات الصحية والتعليمية
                3. دعم المشاريع الصغيرة والمتوسطة
                4. تطوير المناطق العشوائية
                5. تعزيز السياحة والتراث
                
                معاً سنبني قاهرة أفضل للأجيال القادمة.
                ''',
                'summary': 'خطاب ترشح يركز على التطوير الشامل للقاهرة وتحسين الخدمات العامة',
                'facebook_post': '🎤 خطاب الترشح الرسمي\n\nمعاً سنبني قاهرة أفضل للأجيال القادمة\n\n#عمدة_القاهرة #التطوير_الشامل #مستقبل_أفضل',
                'twitter_post': '🎤 خطاب الترشح - معاً سنبني قاهرة أفضل #عمدة_القاهرة #التطوير_الشامل',
                'is_published': True
            }
        )
        if created:
            self.stdout.write('Created sample speech')
        
        # Create sample polls
        polls_data = [
            {
                'title': 'أولويات التطوير في القاهرة',
                'question': 'ما هي أولويتك الأولى لتطوير القاهرة؟',
                'options': [
                    'تطوير النقل العام والمترو',
                    'تحسين الخدمات الصحية',
                    'تطوير التعليم',
                    'دعم المشاريع الصغيرة',
                    'تطوير المناطق العشوائية'
                ],
                'is_anonymous': True,
                'allows_multiple_answers': False,
            },
            {
                'title': 'وسائل التواصل المفضلة',
                'question': 'كيف تفضل التواصل مع العمدة؟',
                'options': [
                    'تطبيق الهاتف المحمول',
                    'الموقع الإلكتروني',
                    'صفحات التواصل الاجتماعي',
                    'اللقاءات المباشرة',
                    'الهاتف'
                ],
                'is_anonymous': True,
                'allows_multiple_answers': True,
            }
        ]
        
        for poll_data in polls_data:
            poll, created = Poll.objects.get_or_create(
                candidate=candidate,
                title=poll_data['title'],
                defaults=poll_data
            )
            if created:
                self.stdout.write(f'Created poll: {poll.title}')
        
        # Create sample bot users and supporters
        sample_users = [
            {'telegram_id': 1001, 'username': 'user1', 'first_name': 'محمد', 'last_name': 'أحمد', 'phone_number': '+201111111111'},
            {'telegram_id': 1002, 'username': 'user2', 'first_name': 'فاطمة', 'last_name': 'محمد', 'phone_number': '+201111111112'},
            {'telegram_id': 1003, 'username': 'user3', 'first_name': 'علي', 'last_name': 'حسن', 'phone_number': '+201111111113'},
            {'telegram_id': 1004, 'username': 'user4', 'first_name': 'نور', 'last_name': 'إبراهيم', 'phone_number': '+201111111114'},
            {'telegram_id': 1005, 'username': 'user5', 'first_name': 'يوسف', 'last_name': 'عبدالله', 'phone_number': '+201111111115'},
        ]
        
        for user_data in sample_users:
            bot_user, created = BotUser.objects.get_or_create(
                bot=bot,
                telegram_id=user_data['telegram_id'],
                defaults={
                    'username': user_data['username'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'phone_number': user_data['phone_number'],
                    'started_at': timezone.now(),
                    'last_seen_at': timezone.now(),
                }
            )
            
            if created:
                # Create supporter record
                Supporter.objects.create(
                    candidate=candidate,
                    bot_user=bot_user,
                    city='القاهرة',
                    district='المعادي' if user_data['telegram_id'] in [1001, 1002] else 'الزمالك',
                    latitude=29.9600 if user_data['telegram_id'] in [1001, 1002] else 30.0626,
                    longitude=31.2600 if user_data['telegram_id'] in [1001, 1002] else 31.2197,
                    support_level=5,
                    notes=f'مؤيد نشط - {user_data["first_name"]} {user_data["last_name"]}'
                )
                
                # Create volunteer for some users
                if user_data['telegram_id'] in [1001, 1002, 1003]:
                    volunteer = Volunteer.objects.create(
                        candidate=candidate,
                        bot_user=bot_user,
                        name=f"{user_data['first_name']} {user_data['last_name']}",
                        phone=user_data['phone_number'],
                        role='volunteer',
                        is_active=True
                    )
                    
                    # Create some volunteer activities
                    activities = [
                        {
                            'activity_type': 'canvassing',
                            'description': 'زيارة منزلية في المعادي',
                            'supporters_contacted': 5,
                            'hours_worked': 3.0,
                            'location': 'المعادي'
                        },
                        {
                            'activity_type': 'posters',
                            'description': 'توزيع ملصقات في الزمالك',
                            'posters_distributed': 50,
                            'hours_worked': 2.0,
                            'location': 'الزمالك'
                        }
                    ]
                    
                    for activity_data in activities:
                        VolunteerActivity.objects.create(
                            volunteer=volunteer,
                            **activity_data
                        )
        
        self.stdout.write('Created sample bot users, supporters, and volunteers')
        
        # Create sample fake news alerts
        fake_news_data = [
            {
                'title': 'أحمد محمد علي متورط في فضيحة مالية',
                'content': 'تقارير غير مؤكدة تشير إلى تورط المرشح في قضايا مالية',
                'source_url': 'https://fake-news-site.com/article1',
                'source_platform': 'facebook',
                'severity': 'high',
                'is_verified': False,
            },
            {
                'title': 'المرشح يعد بإلغاء رسوم النقل العام',
                'content': 'وعد غير واقعي بإلغاء جميع رسوم النقل العام',
                'source_url': 'https://misleading-news.com/article2',
                'source_platform': 'twitter',
                'severity': 'medium',
                'is_verified': True,
            }
        ]
        
        for alert_data in fake_news_data:
            alert, created = FakeNewsAlert.objects.get_or_create(
                candidate=candidate,
                title=alert_data['title'],
                defaults=alert_data
            )
            if created:
                self.stdout.write(f'Created fake news alert: {alert.title}')
        
        # Create sample daily questions
        questions_data = [
            {
                'question': 'ما هي خطتك لتحسين النقل العام في القاهرة؟',
                'answer': 'خطتنا تشمل توسيع شبكة المترو وإنشاء خطوط حافلات سريعة وذكية',
                'is_answered': True,
                'is_public': True,
            },
            {
                'question': 'كيف ستتعامل مع مشكلة التلوث في القاهرة؟',
                'answer': 'سنعمل على تطبيق معايير بيئية صارمة وتشجيع النقل النظيف',
                'is_answered': True,
                'is_public': True,
            },
            {
                'question': 'ما هي أولويتك في تطوير التعليم؟',
                'answer': '',  # Unanswered question
                'is_answered': False,
                'is_public': True,
            }
        ]
        
        for i, question_data in enumerate(questions_data):
            bot_user = BotUser.objects.filter(bot=bot).first()
            if bot_user:
                question, created = DailyQuestion.objects.get_or_create(
                    candidate=candidate,
                    bot_user=bot_user,
                    question=question_data['question'],
                    defaults={
                        'answer': question_data['answer'],
                        'is_answered': question_data['is_answered'],
                        'is_public': question_data['is_public'],
                        'answered_at': timezone.now() if question_data['is_answered'] else None,
                    }
                )
                if created:
                    self.stdout.write(f'Created question: {question.question[:50]}...')
        
        # Create campaign analytics
        analytics, created = CampaignAnalytics.objects.get_or_create(candidate=candidate)
        if created:
            self.stdout.write('Created campaign analytics')
        
        self.stdout.write(
            self.style.SUCCESS('Sample data created successfully!')
        )
        self.stdout.write('\n=== ACCESS LINKS ===')
        self.stdout.write('Admin Panel: https://3ad99fb5c246.ngrok-free.app/admin/')
        self.stdout.write('Election Dashboard: https://3ad99fb5c246.ngrok-free.app/hub/election-dashboard/')
        self.stdout.write('Main Dashboard: https://3ad99fb5c246.ngrok-free.app/hub/')
        self.stdout.write('\nLogin credentials: admin / admin123')
