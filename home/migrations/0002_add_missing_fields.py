# Generated migration for adding missing fields

import django.core.validators
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0001_initial'),
    ]

    operations = [
        # Add missing fields to Book model
        migrations.AddField(
            model_name='book',
            name='cover_image',
            field=models.ImageField(blank=True, null=True, upload_to='book_covers/'),
        ),
        migrations.AddField(
            model_name='book',
            name='publication_year',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='book',
            name='publisher',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='book',
            name='date_added',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        
        # Update Book ordering
        migrations.AlterModelOptions(
            name='book',
            options={'ordering': ['-date_added', 'name']},
        ),
        
        # Add missing fields to Student model
        migrations.AddField(
            model_name='student',
            name='date_joined',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='student',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        
        # Add missing field to IssuedBook model
        migrations.AddField(
            model_name='issuedbook',
            name='fine_paid',
            field=models.BooleanField(default=False),
        ),
        
        # Add unique_together constraint
        migrations.AlterUniqueTogether(
            name='issuedbook',
            unique_together={('student', 'book')},
        ),
    ]
