# Generated migration to update models for improved library management

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0002_add_missing_fields'),
    ]

    operations = [
        # Change ISBN from PositiveIntegerField to CharField with validator
        migrations.AlterField(
            model_name='book',
            name='isbn',
            field=models.CharField(
                max_length=13,
                unique=True,
                validators=[django.core.validators.RegexValidator(
                    message='ISBN must be 10 or 13 digits',
                    regex='^\\d{10}(\\d{3})?$'
                )],
                help_text='Enter 10 or 13 digit ISBN'
            ),
        ),
        
        # Make classroom and branch optional with defaults
        migrations.AlterField(
            model_name='student',
            name='classroom',
            field=models.CharField(blank=True, default='N/A', max_length=10),
        ),
        migrations.AlterField(
            model_name='student',
            name='branch',
            field=models.CharField(blank=True, default='N/A', max_length=10),
        ),
        
        # Add phone validator
        migrations.AlterField(
            model_name='student',
            name='phone',
            field=models.CharField(
                blank=True,
                max_length=10,
                validators=[django.core.validators.RegexValidator(
                    message='Phone number must be exactly 10 digits',
                    regex='^\\d{10}$'
                )]
            ),
        ),
        
        # Add returned_date field to IssuedBook
        migrations.AddField(
            model_name='issuedbook',
            name='returned_date',
            field=models.DateField(blank=True, null=True),
        ),
        
        # Add fine_amount field to IssuedBook
        migrations.AddField(
            model_name='issuedbook',
            name='fine_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        
        # Add related_name to foreign keys
        migrations.AlterField(
            model_name='issuedbook',
            name='student',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='issued_books',
                to='home.student'
            ),
        ),
        migrations.AlterField(
            model_name='issuedbook',
            name='book',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='issues',
                to='home.book'
            ),
        ),
        
        # Remove unique_together constraint
        migrations.AlterUniqueTogether(
            name='issuedbook',
            unique_together=set(),
        ),
        
        # Add database indexes for better performance
        migrations.AddIndex(
            model_name='issuedbook',
            index=models.Index(fields=['student', 'returned_date'], name='home_issued_student_ret_idx'),
        ),
        migrations.AddIndex(
            model_name='issuedbook',
            index=models.Index(fields=['book', 'returned_date'], name='home_issued_book_ret_idx'),
        ),
        migrations.AddIndex(
            model_name='issuedbook',
            index=models.Index(fields=['expiry_date'], name='home_issued_expiry_idx'),
        ),
    ]
