from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import IntegrityError, transaction, models
from django.core.paginator import Paginator
from django.db.models import Q, Count, F, Sum, Avg
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from .models import Book, Student, IssuedBook, Category, Subject, Teacher
from .forms import IssueBookForm, AddBookForm, ReturnBookForm, EditBookForm, SubjectForm, TeacherForm
from django.core.exceptions import ValidationError
from datetime import date, timedelta
import csv
import qrcode
import io
from django.core.files.base import ContentFile

@login_required(login_url='/login/')
def index(request):
    """Home page showing all books with search, filter, and pagination"""
    
    # Get all books with optimized queries
    books = Book.objects.select_related('category').prefetch_related(
        'issues'
    ).annotate(
        issued_count=Count('issues', filter=Q(issues__returned_date__isnull=True))
    )
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        books = books.filter(
            Q(name__icontains=search_query) |
            Q(author__icontains=search_query) |
            Q(isbn__icontains=search_query)
        )
    
    # Category filter
    category_id = request.GET.get('category')
    if category_id:
        books = books.filter(category_id=category_id)
    
    # Availability filter
    availability = request.GET.get('availability')
    if availability == 'available':
        # Filter books that have at least one copy remaining
        books = books.annotate(
            available_qty=F('quantity') - Count('issues', filter=Q(issues__returned_date__isnull=True))
        ).filter(available_qty__gt=0)
    elif availability == 'unavailable':
        # Filter books with no copies remaining
        books = books.annotate(
            available_qty=F('quantity') - Count('issues', filter=Q(issues__returned_date__isnull=True))
        ).filter(available_qty__lte=0)
    
    # Sort
    sort_by = request.GET.get('sort', '-date_added')
    
    if sort_by in ['name', '-name', 'author', '-author', 'date_added', '-date_added']:
        books = books.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(books, 12)  # 12 books per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all categories for filter dropdown
    categories = Category.objects.all().order_by('name')
    
    # Library Statistics for Dashboard
    total_books = Book.objects.count()
    total_quantity = Book.objects.aggregate(total=Sum('quantity'))['total'] or 0
    total_issued = IssuedBook.objects.filter(returned_date__isnull=True).count()
    total_available = total_quantity - total_issued
    
    # Recent & Popular Books
    recent_books = Book.objects.select_related('category').order_by('-date_added')[:6]
    popular_books = Book.objects.select_related('category').annotate(
        issue_count=Count('issues')
    ).order_by('-issue_count')[:6]

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_id,
        'selected_availability': availability,
        'selected_sort': sort_by,
        'total_books': total_books,
        'total_quantity': total_quantity,
        'total_issued': total_issued,
        'total_available': total_available,
        'recent_books': recent_books,
        'popular_books': popular_books,
    }
    
    return render(request, 'home/index.html', context)

@login_required(login_url='/login/')
@staff_member_required(login_url='/login/')
def add_book(request):
    """Add a new book to the library (staff only)"""
    if request.method == "POST":
        form = AddBookForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                book = form.save()
                messages.success(
                    request, 
                    f"Book '{book.name}' by {book.author} added successfully!"
                )
                return redirect('index')
            except IntegrityError:
                messages.error(
                    request, 
                    "A book with this ISBN already exists in the library."
                )
            except Exception as e:
                messages.error(request, f"Error adding book: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AddBookForm()
    
    categories = Category.objects.all()
    return render(request, "home/add_book.html", {'form': form, 'categories': categories})

@login_required(login_url='/login/')
@staff_member_required(login_url='/login/')
def edit_book(request, book_id):
    """Edit an existing book (staff only)"""
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == "POST":
        form = EditBookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            try:
                # Validate using model's clean method
                updated_book = form.save(commit=False)
                updated_book.full_clean()
                updated_book.save()
                
                messages.success(
                    request,
                    f"Book '{updated_book.name}' updated successfully!"
                )
                return redirect('index')
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
            except Exception as e:
                messages.error(request, f"Error updating book: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = EditBookForm(instance=book)
    
    categories = Category.objects.all()
    return render(request, "home/edit_book.html", {
        'form': form,
        'book': book,
        'categories': categories
    })

@login_required(login_url='/login/')
def issue_book(request):
    """Issue a book to a student"""
    # Check if logged-in user has a student profile
    try:
        student = request.user.student
    except Student.DoesNotExist:
        messages.error(
            request,
            "You don't have a student profile. Please contact the administrator."
        )
        return redirect('index')
    
    if request.method == "POST":
        form = IssueBookForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    book = form.cleaned_data['isbn2']
                    student = form.cleaned_data['name2']
                    
                    # Final validation
                    if not student.can_issue_more_books():
                        if not student.is_active:
                            raise ValidationError("Your student account is not active.")
                        elif student.get_overdue_books().exists():
                            raise ValidationError(
                                "You have overdue books. Please return them before issuing new books."
                            )
                        else:
                            raise ValidationError(
                                f"You have reached the maximum limit of {Student.MAX_BOOKS_ALLOWED} books."
                            )
                    
                    obj = IssuedBook()
                    obj.student = student
                    obj.book = book
                    obj.save()
                    
                    messages.success(
                        request,
                        f"Book '{obj.book.name}' issued to {obj.student.user.username} successfully! "
                        f"Due date: {obj.expiry_date.strftime('%Y-%m-%d')}"
                    )
                    return redirect('index')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Error issuing book: {str(e)}")
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = IssueBookForm()
    
    return render(request, "home/issue_book.html", {'form': form})

@login_required(login_url='/login/')
def return_book(request):
    """Return an issued book"""
    if request.method == "POST":
        form = ReturnBookForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    issued_book = form.cleaned_data['issued_book']
                    book_name = issued_book.book.name
                    student_name = issued_book.student.user.username
                    
                    # Mark as returned instead of deleting
                    issued_book.returned_date = timezone.now().date()
                    
                    # Calculate and store fine if overdue
                    if issued_book.is_overdue():
                        days_overdue = abs(issued_book.days_until_due())
                        fine = issued_book.calculate_fine()
                        issued_book.fine_amount = fine
                        issued_book.save()
                        
                        messages.warning(
                            request,
                            f"Book '{book_name}' returned by {student_name}. "
                            f"Note: Book was {days_overdue} day(s) overdue. Fine: ${fine}. "
                            f"Please pay the fine."
                        )
                    else:
                        issued_book.save()
                        messages.success(
                            request,
                            f"Book '{book_name}' returned by {student_name} successfully!"
                        )
                    
                    return redirect('index')
            except Exception as e:
                messages.error(request, f"Error returning book: {str(e)}")
        else:
            messages.error(request, "Please select a book to return.")
    else:
        form = ReturnBookForm()
    
    return render(request, "home/return_book.html", {'form': form})

@login_required(login_url='/login/')
def view_issued_books(request):
    """View all currently issued books with pagination"""
    issued_books = IssuedBook.objects.filter(
        returned_date__isnull=True
    ).select_related(
        'student__user',
        'book__category'
    ).order_by('-issued_date')
    
    # Pagination
    paginator = Paginator(issued_books, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'home/issued_books.html', {'page_obj': page_obj})

@login_required(login_url='/login/')
@staff_member_required(login_url='/login/')
def delete_book(request, myid):
    """Delete a book from the library with safety checks (staff only)"""
    try:
        book = get_object_or_404(Book, id=myid)
        
        # Check if book is currently issued
        issued_count = IssuedBook.objects.filter(
            book=book,
            returned_date__isnull=True
        ).count()
        
        if issued_count > 0:
            messages.error(
                request,
                f"Cannot delete '{book.name}'. {issued_count} copy(ies) currently issued. "
                "Please wait for all copies to be returned."
            )
            return redirect('index')
        
        book_name = book.name
        book.delete()
        messages.success(request, f"Book '{book_name}' deleted successfully!")
    except Exception as e:
        messages.error(request, f"Error deleting book: {str(e)}")
    
    return redirect('index')

@login_required(login_url='/login/')
def view_overdue_books(request):
    """View all overdue books"""
    
    overdue_books = IssuedBook.objects.filter(
        returned_date__isnull=True,
        expiry_date__lt=timezone.now().date()
    ).select_related(
        'student__user',
        'book__category'
    ).order_by('expiry_date')
    
    context = {
        'overdue_books': overdue_books,
        'total_overdue': overdue_books.count(),
    }
    return render(request, "home/overdue_books.html", context)

@login_required(login_url='/login/')
def book_detail(request, book_id):
    """View detailed information about a specific book"""
    book = get_object_or_404(Book.objects.select_related('category'), id=book_id)
    
    # Get issue history for this book
    issue_history = IssuedBook.objects.filter(
        book=book
    ).select_related(
        'student__user'
    ).order_by('-issued_date')[:10]  # Last 10 issues
    
    # Get current issues
    current_issues = IssuedBook.objects.filter(
        book=book,
        returned_date__isnull=True
    ).select_related('student__user')
    
    context = {
        'book': book,
        'issue_history': issue_history,
        'current_issues': current_issues,
        'available_copies': book.available_quantity(),
    }
    return render(request, 'home/book_detail.html', context)

@login_required(login_url='/login/')
def student_dashboard(request):
    """Student dashboard showing their borrowed books and history"""
    try:
        student = request.user.student
    except Student.DoesNotExist:
        messages.error(
            request,
            "You don't have a student profile. Please contact the administrator."
        )
        return redirect('index')
    
    # Currently borrowed books
    current_books = IssuedBook.objects.filter(
        student=student,
        returned_date__isnull=True
    ).select_related('book__category').order_by('-issued_date')
    
    # Book history (returned books)
    book_history = IssuedBook.objects.filter(
        student=student,
        returned_date__isnull=False
    ).select_related('book__category').order_by('-returned_date')[:20]
    
    # Calculate statistics
    total_books_issued = IssuedBook.objects.filter(student=student).count()
    total_books_returned = IssuedBook.objects.filter(
        student=student,
        returned_date__isnull=False
    ).count()
    
    # Overdue books
    overdue_books = current_books.filter(expiry_date__lt=timezone.now().date())
    
    # Total fines
    total_fines = IssuedBook.objects.filter(
        student=student,
        fine_amount__gt=0
    ).aggregate(total=Sum('fine_amount'))['total'] or 0
    
    context = {
        'student': student,
        'current_books': current_books,
        'book_history': book_history,
        'total_books_issued': total_books_issued,
        'total_books_returned': total_books_returned,
        'overdue_books': overdue_books,
        'total_fines': total_fines,
        'can_issue_more': student.can_issue_more_books(),
    }
    return render(request, 'home/student_dashboard.html', context)

@login_required(login_url='/login/')
@staff_member_required(login_url='/login/')
def library_statistics(request):
    """View comprehensive library statistics (staff only)"""
    
    # Book statistics
    total_books = Book.objects.count()
    total_copies = Book.objects.aggregate(total=Sum('quantity'))['total'] or 0
    total_categories = Category.objects.count()
    
    # Currently issued books
    currently_issued = IssuedBook.objects.filter(
        returned_date__isnull=True
    ).count()
    
    # Available books
    available_copies = total_copies - currently_issued
    
    # Student statistics
    total_students = Student.objects.count()
    active_students = Student.objects.filter(is_active=True).count()
    
    # Overdue statistics
    overdue_count = IssuedBook.objects.filter(
        returned_date__isnull=True,
        expiry_date__lt=timezone.now().date()
    ).count()
    
    # Fine statistics
    total_fines = IssuedBook.objects.filter(
        fine_amount__gt=0
    ).aggregate(total=Sum('fine_amount'))['total'] or 0
    
    # Most popular books (most issued)
    popular_books = Book.objects.annotate(
        issue_count=Count('issues')
    ).order_by('-issue_count')[:10]
    
    # Most active students
    active_borrowers = Student.objects.annotate(
        borrow_count=Count('issued_books')
    ).order_by('-borrow_count')[:10]
    
    # Category-wise distribution
    category_stats = Category.objects.annotate(
        book_count=Count('books')
    ).order_by('-book_count')
    
    # Recent activities
    recent_issues = IssuedBook.objects.select_related(
        'student__user',
        'book'
    ).order_by('-issued_date')[:10]
    
    recent_returns = IssuedBook.objects.filter(
        returned_date__isnull=False
    ).select_related(
        'student__user',
        'book'
    ).order_by('-returned_date')[:10]
    
    context = {
        'total_books': total_books,
        'total_copies': total_copies,
        'total_categories': total_categories,
        'currently_issued': currently_issued,
        'available_copies': available_copies,
        'total_students': total_students,
        'active_students': active_students,
        'overdue_count': overdue_count,
        'total_fines': total_fines,
        'popular_books': popular_books,
        'active_borrowers': active_borrowers,
        'category_stats': category_stats,
        'recent_issues': recent_issues,
        'recent_returns': recent_returns,
    }
    return render(request, 'home/library_statistics.html', context)

@login_required(login_url='/login/')
def search_books_api(request):
    """API endpoint for book search autocomplete"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    books = Book.objects.filter(
        Q(name__icontains=query) |
        Q(author__icontains=query) |
        Q(isbn__icontains=query)
    ).select_related('category')[:10]
    
    results = []
    for book in books:
        results.append({
            'id': book.id,
            'name': book.name,
            'author': book.author,
            'isbn': book.isbn,
            'category': book.category.name if book.category else 'N/A',
            'available': book.available_quantity(),
        })
    
    return JsonResponse({'results': results})

@login_required(login_url='/login/')
@staff_member_required(login_url='/login/')
def export_issued_books(request):
    """Export currently issued books to CSV (staff only)"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="issued_books_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Book Name',
        'ISBN',
        'Student Name',
        'Student ID',
        'Issued Date',
        'Due Date',
        'Days Until Due',
        'Status',
        'Fine Amount'
    ])
    
    issued_books = IssuedBook.objects.filter(
        returned_date__isnull=True
    ).select_related(
        'student__user',
        'book'
    ).order_by('-issued_date')
    
    for issued in issued_books:
        days_until_due = issued.days_until_due()
        status = 'Overdue' if issued.is_overdue() else 'Active'
        fine = issued.calculate_fine() if issued.is_overdue() else 0
        
        writer.writerow([
            issued.book.name,
            issued.book.isbn,
            issued.student.user.get_full_name() or issued.student.user.username,
            issued.student.user.username,
            issued.issued_date.strftime('%Y-%m-%d'),
            issued.expiry_date.strftime('%Y-%m-%d'),
            days_until_due,
            status,
            f'${fine}' if fine > 0 else '$0'
        ])
    
    return response

@login_required(login_url='/login/')
@staff_member_required(login_url='/login/')
def renew_book(request, issued_book_id):
    """Renew a book's due date (staff only)"""
    issued_book = get_object_or_404(IssuedBook, id=issued_book_id)
    
    if issued_book.returned_date:
        messages.error(request, "Cannot renew a book that has already been returned.")
        return redirect('view_issued_books')
    
    if request.method == "POST":
        try:
            # Extend due date by 14 days
            days_to_extend = int(request.POST.get('days', 14))
            
            if days_to_extend < 1 or days_to_extend > 30:
                messages.error(request, "Extension must be between 1 and 30 days.")
                return redirect('view_issued_books')
            
            old_expiry = issued_book.expiry_date
            issued_book.expiry_date = old_expiry + timedelta(days=days_to_extend)
            issued_book.save()
            
            messages.success(
                request,
                f"Book '{issued_book.book.name}' for {issued_book.student.user.username} "
                f"renewed successfully! New due date: {issued_book.expiry_date.strftime('%Y-%m-%d')}"
            )
        except Exception as e:
            messages.error(request, f"Error renewing book: {str(e)}")
    
    return redirect('view_issued_books')

@login_required(login_url='/login/')
@staff_member_required(login_url='/login/')
def bulk_delete_books(request):
    """Bulk delete books (staff only)"""
    if request.method == "POST":
        book_ids = request.POST.getlist('book_ids')
        
        if not book_ids:
            messages.error(request, "No books selected for deletion.")
            return redirect('index')
        
        try:
            # Check if any selected books are currently issued
            issued_books = IssuedBook.objects.filter(
                book_id__in=book_ids,
                returned_date__isnull=True
            ).values_list('book__name', flat=True)
            
            if issued_books:
                messages.error(
                    request,
                    f"Cannot delete books that are currently issued: {', '.join(issued_books)}"
                )
                return redirect('index')
            
            # Delete books
            deleted_count = Book.objects.filter(id__in=book_ids).delete()[0]
            messages.success(request, f"Successfully deleted {deleted_count} book(s).")
        except Exception as e:
            messages.error(request, f"Error deleting books: {str(e)}")
    
    return redirect('index')

@login_required(login_url='/login/')
def check_book_availability(request, book_id):
    """API endpoint to check book availability"""
    try:
        book = Book.objects.get(id=book_id)
        available = book.available_quantity()
        
        return JsonResponse({
            'success': True,
            'book_name': book.name,
            'total_quantity': book.quantity,
            'available_quantity': available,
            'currently_issued': book.quantity - available,
            'is_available': available > 0,
        })
    except Book.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Book not found'
        }, status=404)

# Teacher and Subject Views
@login_required
@staff_member_required
def subject_list(request):
    subjects = Subject.objects.all()
    if request.method == "POST":
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Subject added successfully!")
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'home/subject_list.html', {'subjects': subjects, 'form': form})

@login_required
@staff_member_required
def teacher_list(request):
    teachers = Teacher.objects.select_related('user').prefetch_related('subjects')
    return render(request, 'home/teacher_list.html', {'teachers': teachers})

@login_required
@staff_member_required
def add_teacher(request):
    if request.method == "POST":
        form = TeacherForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password'] or 'teacher123',
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name']
                    )
                    teacher = form.save(commit=False)
                    teacher.user = user
                    teacher.save()
                    form.save_m2m() # Save subjects
                    messages.success(request, f"Teacher {user.username} added successfully!")
                    return redirect('teacher_list')
            except Exception as e:
                messages.error(request, f"Error: {e}")
    else:
        form = TeacherForm()
    return render(request, 'home/teacher_form.html', {'form': form, 'title': 'Add Teacher'})

@login_required
def student_qr_code(request, student_id):
    """Generate a QR code for a student's identification"""
    student = get_object_or_404(Student, id=student_id)
    
    # Check if user has permission (self or staff)
    if not request.user.is_staff and request.user.student.id != student.id:
        return HttpResponse("Unauthorized", status=403)
    
    # Create QR code data: student username and a random token/id
    qr_data = f"STUDENT:{student.user.username}:{student.id}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to buffer
    buf = io.BytesIO()
    img.save(buf)
    
    return HttpResponse(buf.getvalue(), content_type="image/png")
