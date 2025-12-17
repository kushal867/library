from django import forms
from django.core.exceptions import ValidationError
from .models import Book, Student, IssuedBook, Category

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
        fields = ['name', 'author', 'isbn', 'category', 'description', 'quantity']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'The Great Gatsby'
            }),
            'author': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'F. Scott Fitzgerald'
            }),
            'isbn': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '9783161484100'
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
            
            # Check if student already has this book
            existing_issue = IssuedBook.objects.filter(student=student, book=book).exists()
            if existing_issue:
                raise ValidationError(
                    f"{student.user.username} has already issued this book."
                )
        
        return cleaned_data

class ReturnBookForm(forms.Form):
    """Form for returning issued books"""
    issued_book = forms.ModelChoiceField(
        queryset=IssuedBook.objects.all(),
        empty_label="Select Issued Book to Return",
        label="Issued Book",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize the display of issued books
        self.fields['issued_book'].label_from_instance = lambda obj: (
            f"{obj.book.name} - {obj.student.user.username} "
            f"(Due: {obj.expiry_date.strftime('%Y-%m-%d')})"
        )
