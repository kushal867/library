from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from .models import Book, Student, IssuedBook, Category
from .forms import IssueBookForm, AddBookForm, ReturnBookForm

@login_required(login_url='/login/')
def index(request):
    """Home page showing all books and statistics"""
    books = Book.objects.all().select_related('category')
    
    # Calculate statistics
    total_books = Book.objects.count()
    total_quantity = sum(book.quantity for book in books)
    total_issued = IssuedBook.objects.count()
    total_available = total_quantity - total_issued
    
    context = {
        'books': books,
        'total_books': total_books,
        'total_quantity': total_quantity,
        'total_issued': total_issued,
        'total_available': total_available,
    }
    return render(request, "home/index.html", context)

@login_required(login_url='/login/')
def add_book(request):
    """Add a new book to the library"""
    if request.method == "POST":
        form = AddBookForm(request.POST)
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
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AddBookForm()
    
    categories = Category.objects.all()
    return render(request, "home/add_book.html", {'form': form, 'categories': categories})

@login_required(login_url='/login/')
def issue_book(request):
    """Issue a book to a student"""
    if request.method == "POST":
        form = IssueBookForm(request.POST)
        if form.is_valid():
            try:
                obj = IssuedBook()
                obj.student = form.cleaned_data['name2']
                obj.book = form.cleaned_data['isbn2']
                obj.save()
                messages.success(
                    request,
                    f"Book '{obj.book.name}' issued to {obj.student.user.username} successfully! "
                    f"Due date: {obj.expiry_date.strftime('%Y-%m-%d')}"
                )
                return redirect('index')
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
                issued_book = form.cleaned_data['issued_book']
                book_name = issued_book.book.name
                student_name = issued_book.student.user.username
                
                # Check if overdue
                if issued_book.is_overdue():
                    days_overdue = abs(issued_book.days_until_due())
                    messages.warning(
                        request,
                        f"Book '{book_name}' returned by {student_name}. "
                        f"Note: Book was {days_overdue} day(s) overdue."
                    )
                else:
                    messages.success(
                        request,
                        f"Book '{book_name}' returned by {student_name} successfully!"
                    )
                
                issued_book.delete()
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
    """View all currently issued books"""
    issued_books = IssuedBook.objects.all().select_related('book', 'student__user')
    
    context = {
        'issued_books': issued_books,
        'total_issued': issued_books.count(),
    }
    return render(request, "home/issued_books.html", context)

@login_required(login_url='/login/')
def delete_book(request, myid):
    """Delete a book from the library with safety checks"""
    try:
        book = get_object_or_404(Book, id=myid)
        
        # Check if book is currently issued
        issued_count = IssuedBook.objects.filter(book=book).count()
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
