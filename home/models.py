from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
import re

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

class Book(models.Model):
    name = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    isbn = models.CharField(
        max_length=13,
        unique=True,
        validators=[RegexValidator(
            regex=r'^\d{10}(\d{3})?$',
            message='ISBN must be 10 or 13 digits'
        )],
        help_text='Enter 10 or 13 digit ISBN'
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(
        default=1, 
        validators=[MinValueValidator(1, message="Quantity must be at least 1")]
    )
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    publication_year = models.PositiveIntegerField(blank=True, null=True)
    publisher = models.CharField(max_length=200, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} by {self.author} [{self.isbn}]"
    
    def available_quantity(self):
        """Calculate available copies (total - currently issued)"""
        return self.quantity - self.currently_issued_count()
    
    def currently_issued_count(self):
        """Get count of currently issued copies"""
        return IssuedBook.objects.filter(book=self, returned_date__isnull=True).count()
    
    def clean(self):
        """Validate book data"""
        super().clean()
        
        # Validate publication year is not in future
        if self.publication_year:
            current_year = timezone.now().year
            if self.publication_year > current_year:
                raise ValidationError({
                    'publication_year': f'Publication year cannot be in the future (current year: {current_year})'
                })
        
        # If updating existing book, check quantity is not below issued count
        if self.pk:
            currently_issued = IssuedBook.objects.filter(book=self, returned_date__isnull=True).count()
            if self.quantity < currently_issued:
                raise ValidationError({
                    'quantity': f'Cannot reduce quantity to {self.quantity}. {currently_issued} copies are currently issued.'
                })
    
    def is_available(self):
        """Check if at least one copy is available"""
        return self.available_quantity() > 0
    
    def times_issued(self):
        """Get total number of times this book has been issued"""
        return IssuedBook.objects.filter(book=self).count()
    
    class Meta:
        ordering = ['-date_added', 'name']

class Student(models.Model):
    MAX_BOOKS_ALLOWED = 5  # Maximum books a student can issue at once
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    classroom = models.CharField(max_length=10, blank=True, default='N/A')
    branch = models.CharField(max_length=10, blank=True, default='N/A')
    roll_no = models.CharField(max_length=3, blank=True)
    phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(
            regex=r'^\d{10}$',
            message='Phone number must be exactly 10 digits'
        )]
    )
    image = models.ImageField(upload_to="student_images/", blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.branch} [{self.classroom}]"
    
    def active_issues_count(self):
        """Count of currently issued books"""
        return IssuedBook.objects.filter(student=self, returned_date__isnull=True).count()
    
    def can_issue_more_books(self):
        """Check if student can issue more books"""
        if not self.is_active:
            return False
        if self.active_issues_count() >= self.MAX_BOOKS_ALLOWED:
            return False
        # Check if student has overdue books
        if self.get_overdue_books().exists():
            return False
        return True
    
    def get_overdue_books(self):
        """Get all overdue books for this student"""
        return IssuedBook.objects.filter(
            student=self,
            returned_date__isnull=True,
            expiry_date__lt=timezone.now().date()
        )
    
    def total_fines(self):
        """Calculate total unpaid fines for this student"""
        # Fines from currently overdue books (not yet returned)
        overdue_books = self.get_overdue_books()
        current_overdue_fines = sum(book.calculate_fine() for book in overdue_books)
        
        # Fines from books already returned but hasn't been paid
        unpaid_returned_fines = IssuedBook.objects.filter(
            student=self,
            returned_date__isnull=False,
            fine_amount__gt=0,
            fine_paid=False
        ).aggregate(total=models.Sum('fine_amount'))['total'] or 0
        
        return current_overdue_fines + float(unpaid_returned_fines)
    
    @property
    def has_overdue_books(self):
        """Quick check if student has any overdue books"""
        return self.get_overdue_books().exists()

    @property
    def active_fines(self):
        """Calculate total unpaid fines for this student"""
        return self.total_fines()

    class Meta:
        ordering = ['user__username']

class IssuedBook(models.Model):
    FINE_PER_DAY = 5  # Fine amount per day in currency units
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='issued_books')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='issues')
    issued_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField()
    returned_date = models.DateField(null=True, blank=True)
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fine_paid = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.student.user.username} - {self.book.name}"
    
    def save(self, *args, **kwargs):
        # Set expiry date on creation if not already set
        if not self.expiry_date:
            from datetime import timedelta
            self.expiry_date = timezone.now().date() + timedelta(days=14)
        super().save(*args, **kwargs)
    
    def is_overdue(self):
        """Check if the book is overdue (and not yet returned)"""
        if self.returned_date:
            return False
        return timezone.now().date() > self.expiry_date
    
    def days_until_due(self):
        """Calculate days until due (negative if overdue)"""
        delta = self.expiry_date - timezone.now().date()
        return delta.days
    
    def calculate_fine(self):
        """Calculate fine amount for overdue book"""
        if self.returned_date:
            # Already returned, use stored fine_amount
            return self.fine_amount
        
        if self.is_overdue():
            days_overdue = abs(self.days_until_due())
            return days_overdue * self.FINE_PER_DAY
        return 0
    
    def days_overdue(self):
        """Get number of days overdue (positive number, 0 if not overdue)"""
        if self.is_overdue():
            return abs(self.days_until_due())
        return 0
    
    class Meta:
        ordering = ['-issued_date']
        verbose_name = "Issued Book"
        verbose_name_plural = "Issued Books"
        indexes = [
            models.Index(fields=['student', 'returned_date']),
            models.Index(fields=['book', 'returned_date']),
            models.Index(fields=['expiry_date']),
        ]

class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ['name']

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    subjects = models.ManyToManyField(Subject, related_name='teachers')
    department = models.CharField(max_length=100)
    phone = models.CharField(
        max_length=10,
        validators=[RegexValidator(
            regex=r'^\d{10}$',
            message='Phone number must be exactly 10 digits'
        )]
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Prof. {self.user.get_full_name() or self.user.username}"

    class Meta:
        ordering = ['user__last_name', 'user__first_name']

