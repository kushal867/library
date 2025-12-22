from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import IntegrityError, transaction, models
from django.core.paginator import Paginator
from django.db.models import Q, Count, F
from .models import Book, Student, IssuedBook, Category
from .forms import IssueBookForm, AddBookForm, ReturnBookForm, EditBookForm

@login_required(login_url='/login/')
def index(request):
    """Home page showing all books with search, filter, and pagination"""
    # Annotate books with currently_issued count for efficient filtering
    books_list = Book.objects.all().select_related('category').annotate(
        currently_issued=Count('issues', filter=Q(issues__returned_date__isnull=True))
    )
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        books_list = books_list.filter(
            Q(name__icontains=search_query) |
            Q(author__icontains=search_query) |
            Q(isbn__icontains=search_query)
        )
    
    # Filter by category
    category_filter = request.GET.get('category', '')
    if category_filter:
        books_list = books_list.filter(category_id=category_filter)
    
    # Filter by availability - now using database-level filtering
    availability_filter = request.GET.get('availability', '')
    if availability_filter == 'available':
        # Only show books with available copies (quantity > currently_issued)
        books_list = books_list.filter(quantity__gt=F('currently_issued'))
    elif availability_filter == 'unavailable':
        # Show books with no available copies (quantity <= currently_issued)
        books_list = books_list.filter(quantity__lte=F('currently_issued'))
    
    # Pagination (25 books per page)
    paginator = Paginator(books_list, 25)
    page_number = request.GET.get('page')
    books = paginator.get_page(page_number)
    
    # Calculate statistics
    total_books = Book.objects.count()
    total_quantity = sum(book.quantity for book in Book.objects.all())
    total_issued = IssuedBook.objects.filter(returned_date__isnull=True).count()
    total_available = total_quantity - total_issued
    
    # Get categories for filter dropdown
    categories = Category.objects.all()
    
    context = {
        'books': books,
        'total_books': total_books,
        'total_quantity': total_quantity,
        'total_issued': total_issued,
        'total_available': total_available,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'availability_filter': availability_filter,
    }
    return render(request, "home/index.html", context)

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
                    from datetime import date
                    issued_book.returned_date = date.today()
                    
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
    issued_books_list = IssuedBook.objects.filter(
        returned_date__isnull=True
    ).select_related('book', 'student__user')
    
    # Pagination
    paginator = Paginator(issued_books_list, 25)
    page_number = request.GET.get('page')
    issued_books = paginator.get_page(page_number)
    
    context = {
        'issued_books': issued_books,
        'total_issued': issued_books_list.count(),
    }
    return render(request, "home/issued_books.html", context)

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
    from datetime import date
    overdue_books = IssuedBook.objects.filter(
        returned_date__isnull=True,
        expiry_date__lt=date.today()
    ).select_related('book', 'student__user')
    
    context = {
        'overdue_books': overdue_books,
        'total_overdue': overdue_books.count(),
    }
    return render(request, "home/overdue_books.html", context)
