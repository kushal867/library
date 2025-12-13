from django.contrib import admin
from .models import Book, Student, Category, IssuedBook

admin.site.register(Book)
admin.site.register(Student)
admin.site.register(Category)
admin.site.register(IssuedBook)
