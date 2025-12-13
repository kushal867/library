from django import forms
from .models import Book, Student, IssuedBook

class IssueBookForm(forms.Form):
    isbn2 = forms.ModelChoiceField(queryset=Book.objects.all(), empty_label="Book Name [ISBN]", to_field_name="isbn", label="Book Name/ISBN")
    name2 = forms.ModelChoiceField(queryset=Student.objects.all(), empty_label="Name [Class] [Branch]", to_field_name="user", label="Student Details")
    
    isbn2.widget.attrs.update({'class': 'form-control'})
    name2.widget.attrs.update({'class':'form-control'})
