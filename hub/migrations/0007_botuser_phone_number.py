from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hub', '0006_bot_description_bot_image_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='botuser',
            name='phone_number',
            field=models.CharField(max_length=32, blank=True, null=True),
        ),
    ]


