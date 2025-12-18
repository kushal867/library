from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

class Book(models.Model):
    name = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    isbn = models.PositiveIntegerField(unique=True)
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
        issued_count = IssuedBook.objects.filter(book=self).count()
        return self.quantity - issued_count
    
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
    classroom = models.CharField(max_length=10)
    branch = models.CharField(max_length=10)
    roll_no = models.CharField(max_length=3, blank=True)
    phone = models.CharField(max_length=10, blank=True)
    image = models.ImageField(upload_to="student_images/", blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.branch} [{self.classroom}]"
    
    def active_issues_count(self):
        """Count of currently issued books"""
        return IssuedBook.objects.filter(student=self).count()
    
    def can_issue_more_books(self):
        """Check if student can issue more books"""
        return self.is_active and self.active_issues_count() < self.MAX_BOOKS_ALLOWED
    
    def get_overdue_books(self):
        """Get all overdue books for this student"""
        return IssuedBook.objects.filter(
            student=self,
            expiry_date__lt=datetime.today().date()
        )
    
    class Meta:
        ordering = ['user__username']

class IssuedBook(models.Model):
    FINE_PER_DAY = 5  # Fine amount per day in currency units
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    issued_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField()
    fine_paid = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.student.user.username} - {self.book.name}"
    
    def save(self, *args, **kwargs):
        # Set expiry date on creation if not already set
        if not self.expiry_date:
            self.expiry_date = datetime.today().date() + timedelta(days=14)
        super().save(*args, **kwargs)
    
    def is_overdue(self):
        """Check if the book is overdue"""
        return datetime.today().date() > self.expiry_date
    
    def days_until_due(self):
        """Calculate days until due (negative if overdue)"""
        delta = self.expiry_date - datetime.today().date()
        return delta.days
    
    def calculate_fine(self):
        """Calculate fine amount for overdue book"""
        if self.is_overdue():
            days_overdue = abs(self.days_until_due())
            return days_overdue * self.FINE_PER_DAY
        return 0
    
    class Meta:
        ordering = ['-issued_date']
        verbose_name = "Issued Book"
        verbose_name_plural = "Issued Books"
        # Prevent same book from being issued to same student multiple times
        unique_together = ['student', 'book']
