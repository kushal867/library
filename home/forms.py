from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import Book, Student, IssuedBook, Category, Subject, Teacher

class AddBookForm(forms.ModelForm):
    """Form for adding new books to the library"""
    category_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Or enter a new category name'
        }),
        label="New Category (Optional)"
    )
    
    class Meta:
        model = Book
        fields = ['name', 'author', 'isbn', 'category', 'description', 'quantity', 'cover_image', 'publication_year', 'publisher']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'The Great Gatsby'
            }),
            'author': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'F. Scott Fitzgerald'
            }),
            'isbn': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '9783161484100',
                'pattern': r'\d{10}(\d{3})?',
                'title': 'Enter 10 or 13 digit ISBN'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description of the book',
                'rows': 3
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '1',
                'min': '1'
            }),
            'cover_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'publication_year': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '2024',
                'min': '1800',
                'max': '2100'
            }),
            'publisher': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Scribner'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        category_name = cleaned_data.get('category_name')
        
        # If new category name is provided, create or get it
        if category_name:
            category_obj, created = Category.objects.get_or_create(name=category_name)
            cleaned_data['category'] = category_obj
        elif not category:
            raise ValidationError("Please select a category or enter a new category name.")
        
        return cleaned_data

class IssueBookForm(forms.Form):
    """Form for issuing books to students"""
    isbn2 = forms.ModelChoiceField(
        queryset=Book.objects.all(), 
        empty_label="Select Book", 
        to_field_name="isbn", 
        label="Book Name/ISBN",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    name2 = forms.ModelChoiceField(
        queryset=Student.objects.all(), 
        empty_label="Select Student", 
        to_field_name="user", 
        label="Student Details",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        book = cleaned_data.get('isbn2')
        student = cleaned_data.get('name2')
        
        if book and student:
            # Check if book is available
            if not book.is_available():
                raise ValidationError(
                    f"'{book.name}' is not available. All {book.quantity} copies are currently issued."
                )
            
            # Check if student already has this book issued (and not returned)
            existing_issue = IssuedBook.objects.filter(
                student=student,
                book=book,
                returned_date__isnull=True
            ).exists()
            if existing_issue:
                raise ValidationError(
                    f"{student.user.username} has already issued this book and not returned it."
                )
            
            # Check if student is active
            if not student.is_active:
                raise ValidationError(
                    f"{student.user.username}'s account is inactive. Please contact administrator."
                )
            
            # Check if student has reached book limit
            if not student.can_issue_more_books():
                active_count = student.active_issues_count()
                overdue_books = student.get_overdue_books()
                
                if overdue_books.exists():
                    raise ValidationError(
                        f"{student.user.username} has {overdue_books.count()} overdue book(s). "
                        "Please return overdue books before issuing new ones."
                    )
                else:
                    raise ValidationError(
                        f"{student.user.username} has reached the maximum limit of "
                        f"{Student.MAX_BOOKS_ALLOWED} books (currently has {active_count})."
                    )
        
        return cleaned_data

class ReturnBookForm(forms.Form):
    """Form for returning issued books"""
    issued_book = forms.ModelChoiceField(
        queryset=IssuedBook.objects.filter(returned_date__isnull=True),
        empty_label="Select Issued Book to Return",
        label="Issued Book",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show books that haven't been returned
        self.fields['issued_book'].queryset = IssuedBook.objects.filter(
            returned_date__isnull=True
        ).select_related('book', 'student__user')
        
        # Customize the display of issued books
        self.fields['issued_book'].label_from_instance = lambda obj: (
            f"{obj.book.name} - {obj.student.user.username} "
            f"(Due: {obj.expiry_date.strftime('%Y-%m-%d')})"
            f"{' - OVERDUE' if obj.is_overdue() else ''}"
        )


class EditBookForm(forms.ModelForm):
    """Form for editing existing books"""
    category_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Or enter a new category name'
        }),
        label="New Category (Optional)"
    )
    
    class Meta:
        model = Book
        fields = ['name', 'author', 'isbn', 'category', 'description', 'quantity', 'cover_image', 'publication_year', 'publisher']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'publication_year': forms.NumberInput(attrs={'class': 'form-control', 'min': '1800', 'max': '2100'}),
            'publisher': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        category_name = cleaned_data.get('category_name')
        
        if category_name:
            category_obj, created = Category.objects.get_or_create(name=category_name)
            cleaned_data['category'] = category_obj
        elif not category:
            raise ValidationError("Please select a category or enter a new category name.")
        
        return cleaned_data

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mathematics'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MATH101'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class TeacherForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False)

    class Meta:
        model = Teacher
        fields = ['department', 'phone', 'subjects', 'is_active']
        widgets = {
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'subjects': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

