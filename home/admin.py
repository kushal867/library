from django.contrib import admin
from django.utils.html import format_html
from .models import Book, Student, Category, IssuedBook


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'book_count']
    search_fields = ['name']
    
    def book_count(self, obj):
        count = obj.book_set.count()
        return format_html('<strong>{}</strong>', count)
    book_count.short_description = 'Total Books'


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['name', 'author', 'isbn', 'category', 'quantity', 'available_quantity', 'cover_preview', 'date_added']
    list_filter = ['category', 'date_added', 'publication_year']
    search_fields = ['name', 'author', 'isbn', 'publisher']
    readonly_fields = ['date_added', 'times_issued']
    list_per_page = 25
    date_hierarchy = 'date_added'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'author', 'isbn', 'category')
        }),
        ('Publication Details', {
            'fields': ('publisher', 'publication_year', 'description')
        }),
        ('Inventory', {
            'fields': ('quantity', 'cover_image')
        }),
        ('Metadata', {
            'fields': ('date_added', 'times_issued'),
            'classes': ('collapse',)
        }),
    )
    
    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" width="50" height="70" />', obj.cover_image.url)
        return '-'
    cover_preview.short_description = 'Cover'
    
    def available_quantity(self, obj):
        available = obj.available_quantity()
        color = 'green' if available > 0 else 'red'
        return format_html('<span style="color: {};">{}</span>', color, available)
    available_quantity.short_description = 'Available'


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['user', 'branch', 'classroom', 'roll_no', 'phone', 'active_books', 'is_active', 'date_joined']
    list_filter = ['branch', 'classroom', 'is_active', 'date_joined']
    search_fields = ['user__username', 'user__email', 'roll_no', 'phone']
    readonly_fields = ['date_joined', 'active_issues_count']
    list_per_page = 25
    date_hierarchy = 'date_joined'
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'image')
        }),
        ('Academic Details', {
            'fields': ('branch', 'classroom', 'roll_no')
        }),
        ('Contact', {
            'fields': ('phone',)
        }),
        ('Status', {
            'fields': ('is_active', 'date_joined', 'active_issues_count')
        }),
    )
    
    def active_books(self, obj):
        count = obj.active_issues_count()
        max_books = Student.MAX_BOOKS_ALLOWED
        color = 'red' if count >= max_books else 'green'
        return format_html('<span style="color: {};">{}/{}</span>', color, count, max_books)
    active_books.short_description = 'Active Issues'


@admin.register(IssuedBook)
class IssuedBookAdmin(admin.ModelAdmin):
    list_display = ['book', 'student', 'issued_date', 'expiry_date', 'status', 'fine_amount', 'fine_paid']
    list_filter = ['issued_date', 'expiry_date', 'fine_paid']
    search_fields = ['book__name', 'student__user__username', 'book__isbn']
    readonly_fields = ['issued_date', 'calculate_fine']
    list_per_page = 25
    date_hierarchy = 'issued_date'
    
    def status(self, obj):
        if obj.is_overdue():
            days = abs(obj.days_until_due())
            return format_html('<span style="color: red; font-weight: bold;">Overdue ({} days)</span>', days)
        else:
            days = obj.days_until_due()
            return format_html('<span style="color: green;">Due in {} days</span>', days)
    status.short_description = 'Status'
    
    def fine_amount(self, obj):
        fine = obj.calculate_fine()
        if fine > 0:
            return format_html('<span style="color: red; font-weight: bold;">${}</span>', fine)
        return '$0'
    fine_amount.short_description = 'Fine'

