"""
Utility functions for the library management system.
This module provides helper functions for common operations.
"""
from decimal import Decimal
from typing import Dict, Any
from django.db.models import Sum, Count, Q
from datetime import date
from django.utils import timezone


def calculate_fine_amount(days_overdue, fine_per_day=5):
    """
    Calculate fine amount for overdue books.
    
    Args:
        days_overdue (int): Number of days the book is overdue
        fine_per_day (int): Fine amount per day
    
    Returns:
        Decimal: Total fine amount
    """
    if days_overdue <= 0:
        return Decimal('0.00')
    return Decimal(str(days_overdue * fine_per_day))


def validate_isbn_format(isbn):
    """
    Validate ISBN format (10 or 13 digits).
    
    Args:
        isbn (str): ISBN to validate
    
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    import re
    
    # Remove any whitespace or hyphens
    cleaned_isbn = re.sub(r'[\s\-]', '', str(isbn))
    
    # Check if it's digits only
    if not cleaned_isbn.isdigit():
        return False, "ISBN must contain only digits"
    
    # Check length
    if len(cleaned_isbn) not in [10, 13]:
        return False, "ISBN must be 10 or 13 digits"
    
    return True, "Valid ISBN format"


def generate_library_statistics():
    """
    Generate comprehensive library statistics.
    
    Returns:
        dict: Dictionary containing various library statistics
    """
    from .models import Book, Student, IssuedBook, Category
    
    # Book statistics
    total_books = Book.objects.count()
    total_copies = Book.objects.aggregate(total=Sum('quantity'))['total'] or 0
    total_categories = Category.objects.count()
    
    # Issue statistics
    active_issues = IssuedBook.objects.filter(returned_date__isnull=True).count()
    total_issues_all_time = IssuedBook.objects.count()
    overdue_books = IssuedBook.objects.filter(
        returned_date__isnull=True,
        expiry_date__lt=timezone.now().date()
    ).count()
    
    # Student statistics
    total_students = Student.objects.count()
    active_students = Student.objects.filter(is_active=True).count()
    
    # Fine statistics
    total_fines = 0
    unpaid_fines = 0
    overdue_issues = IssuedBook.objects.filter(
        returned_date__isnull=True,
        expiry_date__lt=timezone.now().date()
    )
    for issue in overdue_issues:
        fine = issue.calculate_fine()
        total_fines += fine
        if not issue.fine_paid:
            unpaid_fines += fine
    
    return {
        'books': {
            'total_titles': total_books,
            'total_copies': total_copies,
            'total_categories': total_categories,
            'available_copies': total_copies - active_issues,
        },
        'issues': {
            'active_issues': active_issues,
            'total_historical': total_issues_all_time,
            'overdue_count': overdue_books,
        },
        'students': {
            'total_students': total_students,
            'active_students': active_students,
        },
        'fines': {
            'total_fines': float(total_fines),
            'unpaid_fines': float(unpaid_fines),
        }
    }


def send_overdue_notification(student):
    """
    Placeholder for sending overdue notification to student.
    Future implementation will send email notifications.
    
    Args:
        student: Student model instance
    
    Returns:
        bool: True if notification would be sent successfully
    """
    # Future implementation: Send email notification
    # from django.core.mail import send_mail
    # 
    # overdue_books = student.get_overdue_books()
    # if not overdue_books.exists():
    #     return False
    # 
    # subject = 'Library Books Overdue Reminder'
    # message = f'Dear {student.user.get_full_name() or student.user.username},\n\n'
    # message += f'You have {overdue_books.count()} overdue book(s):\n\n'
    # 
    # for issue in overdue_books:
    #     days_overdue = issue.days_overdue()
    #     fine = issue.calculate_fine()
    #     message += f'- {issue.book.name} (Overdue by {days_overdue} days, Fine: ${fine})\n'
    # 
    # message += '\nPlease return the books as soon as possible.\n\n'
    # message += 'Best regards,\nLibrary Management'
    # 
    # send_mail(subject, message, 'library@example.com', [student.user.email])
    
    # For now, just return True indicating it would be sent
    return True


def get_popular_books(limit=10):
    """
    Get most popular books based on number of times issued.
    
    Args:
        limit (int): Number of books to return
    
    Returns:
        QuerySet: Top books ordered by popularity
    """
    from .models import Book
    
    return Book.objects.annotate(
        times_issued_count=Count('issues')
    ).order_by('-times_issued_count')[:limit]


def get_student_book_history(student):
    """
    Get complete borrowing history for a student.
    
    Args:
        student: Student model instance
    
    Returns:
        QuerySet: All issued books for this student
    """
    from .models import IssuedBook
    
    return IssuedBook.objects.filter(
        student=student
    ).select_related('book').order_by('-issued_date')
def get_filtered_books(search_query='', category_id=None, availability=None, sort_by='-date_added'):
    """
    Get books with search, filter, and sorting applied.
    """
    from .models import Book
    
    books = Book.objects.select_related('category').prefetch_related(
        'issues'
    ).annotate(
        issued_count=Count('issues', filter=Q(issues__returned_date__isnull=True))
    )

    if search_query:
        books = books.filter(
            Q(name__icontains=search_query) |
            Q(author__icontains=search_query) |
            Q(isbn__icontains=search_query)
        )

    if category_id:
        books = books.filter(category_id=category_id)

    if availability == 'available':
        books = books.annotate(
            available_qty=F('quantity') - Count('issues', filter=Q(issues__returned_date__isnull=True))
        ).filter(available_qty__gt=0)
    elif availability == 'unavailable':
        books = books.annotate(
            available_qty=F('quantity') - Count('issues', filter=Q(issues__returned_date__isnull=True))
        ).filter(available_qty__lte=0)

    if sort_by in ['name', '-name', 'author', '-author', 'date_added', '-date_added']:
        books = books.order_by(sort_by)
    
    return books


def get_dashboard_stats():
    """
    Calculate essential statistics for the library dashboard.
    """
    from .models import Book, IssuedBook, Category
    from django.db.models import Sum

    total_books = Book.objects.count()
    total_quantity = Book.objects.aggregate(total=Sum('quantity'))['total'] or 0
    total_issued = IssuedBook.objects.filter(returned_date__isnull=True).count()
    
    overdue_count = IssuedBook.objects.filter(
        returned_date__isnull=True,
        expiry_date__lt=timezone.now().date()
    ).count()

    return {
        'total_books': total_books,
        'total_quantity': total_quantity,
        'total_issued': total_issued,
        'total_available': total_quantity - total_issued,
        'overdue_count': overdue_count,
    }
