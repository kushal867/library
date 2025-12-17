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

    def __str__(self):
        return str(self.name) + " [" + str(self.isbn) + "]"
    
    def available_quantity(self):
        """Calculate available copies (total - currently issued)"""
        issued_count = IssuedBook.objects.filter(book=self).count()
        return self.quantity - issued_count
    
    def is_available(self):
        """Check if at least one copy is available"""
        return self.available_quantity() > 0
    
    class Meta:
        ordering = ['name']

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    classroom = models.CharField(max_length=10)
    branch = models.CharField(max_length=10)
    roll_no = models.CharField(max_length=3, blank=True)
    phone = models.CharField(max_length=10, blank=True)
    image = models.ImageField(upload_to="student_images/", blank=True)

    def __str__(self):
        return str(self.user) + " [" + str(self.branch) + "]" + " [" + str(self.classroom) + "]"
    
    def active_issues_count(self):
        """Count of currently issued books"""
        return IssuedBook.objects.filter(student=self).count()
    
    class Meta:
        ordering = ['user__username']

class IssuedBook(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    issued_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField()
    
    def __str__(self):
        return self.student.user.username + " issued " + self.book.name
    
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
    
    class Meta:
        ordering = ['-issued_date']
        verbose_name = "Issued Book"
        verbose_name_plural = "Issued Books"
