from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Book, Student, IssuedBook
from datetime import date


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    book_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'book_count']
    
    def get_book_count(self, obj):
        """Get the number of books in this category"""
        return obj.book_set.count()


class BookSerializer(serializers.ModelSerializer):
    """Serializer for Book model"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    available_quantity = serializers.SerializerMethodField()
    times_issued = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    
    class Meta:
        model = Book
        fields = [
            'id', 'name', 'author', 'isbn', 'category', 'category_name',
            'description', 'quantity', 'available_quantity', 'is_available',
            'cover_image', 'publication_year', 'publisher', 'date_added',
            'times_issued'
        ]
        read_only_fields = ['date_added']
    
    def get_available_quantity(self, obj):
        """Get available quantity of this book"""
        return obj.available_quantity()
    
    def get_times_issued(self, obj):
        """Get total times this book has been issued"""
        return obj.times_issued()
    
    def get_is_available(self, obj):
        """Check if book is available"""
        return obj.is_available()


class BookDetailSerializer(BookSerializer):
    """Detailed serializer for Book with additional information"""
    current_issues = serializers.SerializerMethodField()
    
    class Meta(BookSerializer.Meta):
        fields = BookSerializer.Meta.fields + ['current_issues']
    
    def get_current_issues(self, obj):
        """Get list of current issues for this book"""
        issues = IssuedBook.objects.filter(book=obj, returned_date__isnull=True)
        return IssuedBookSerializer(issues, many=True, context=self.context).data


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic User serializer"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        read_only_fields = ['id', 'username']


class StudentSerializer(serializers.ModelSerializer):
    """Serializer for Student model"""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()
    active_issues_count = serializers.SerializerMethodField()
    can_issue_more_books = serializers.SerializerMethodField()
    total_fines = serializers.SerializerMethodField()
    overdue_books_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = [
            'id', 'user', 'username', 'email', 'full_name', 'classroom',
            'branch', 'roll_no', 'phone', 'image', 'date_joined',
            'is_active', 'active_issues_count', 'can_issue_more_books',
            'total_fines', 'overdue_books_count'
        ]
        read_only_fields = ['user', 'date_joined']
    
    def get_full_name(self, obj):
        """Get student's full name"""
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    
    def get_active_issues_count(self, obj):
        """Get count of currently issued books"""
        return obj.active_issues_count()
    
    def get_can_issue_more_books(self, obj):
        """Check if student can issue more books"""
        return obj.can_issue_more_books()
    
    def get_total_fines(self, obj):
        """Get total fines for this student"""
        return float(obj.total_fines())
    
    def get_overdue_books_count(self, obj):
        """Get count of overdue books"""
        return obj.get_overdue_books().count()


class IssuedBookSerializer(serializers.ModelSerializer):
    """Serializer for IssuedBook model"""
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    book_name = serializers.CharField(source='book.name', read_only=True)
    book_author = serializers.CharField(source='book.author', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()
    calculated_fine = serializers.SerializerMethodField()
    
    class Meta:
        model = IssuedBook
        fields = [
            'id', 'student', 'student_name', 'book', 'book_name', 'book_author',
            'issued_date', 'expiry_date', 'returned_date', 'fine_amount',
            'fine_paid', 'is_overdue', 'days_until_due', 'calculated_fine'
        ]
        read_only_fields = ['issued_date', 'expiry_date']
    
    def get_is_overdue(self, obj):
        """Check if book is overdue"""
        return obj.is_overdue()
    
    def get_days_until_due(self, obj):
        """Get days until due date"""
        return obj.days_until_due()
    
    def get_calculated_fine(self, obj):
        """Get calculated fine amount"""
        return float(obj.calculate_fine())


class IssueBookSerializer(serializers.Serializer):
    """Serializer for issuing a book"""
    book_id = serializers.IntegerField()
    student_id = serializers.IntegerField(required=False)
    
    def validate_book_id(self, value):
        """Validate book exists and is available"""
        try:
            book = Book.objects.get(id=value)
            if not book.is_available():
                raise serializers.ValidationError("This book is not currently available.")
            return value
        except Book.DoesNotExist:
            raise serializers.ValidationError("Book not found.")
    
    def validate_student_id(self, value):
        """Validate student exists and can issue books"""
        if not value:
            return value
        try:
            student = Student.objects.get(id=value)
            if not student.can_issue_more_books():
                if not student.is_active:
                    raise serializers.ValidationError("Student account is not active.")
                elif student.get_overdue_books().exists():
                    raise serializers.ValidationError(
                        "Student has overdue books. Return them before issuing new books."
                    )
                else:
                    raise serializers.ValidationError(
                        f"Student has reached the maximum limit of {Student.MAX_BOOKS_ALLOWED} books."
                    )
            return value
        except Student.DoesNotExist:
            raise serializers.ValidationError("Student not found.")


class ReturnBookSerializer(serializers.Serializer):
    """Serializer for returning a book"""
    issued_book_id = serializers.IntegerField()
    
    def validate_issued_book_id(self, value):
        """Validate issued book exists and is not already returned"""
        try:
            issued_book = IssuedBook.objects.get(id=value)
            if issued_book.returned_date:
                raise serializers.ValidationError("This book has already been returned.")
            return value
        except IssuedBook.DoesNotExist:
            raise serializers.ValidationError("Issued book record not found.")
