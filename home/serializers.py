from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Count
from .models import Category, Book, Student, IssuedBook


class CategorySerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "book_count"]


class BookSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    available_quantity = serializers.SerializerMethodField()
    times_issued = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id",
            "name",
            "author",
            "isbn",
            "category",
            "category_name",
            "description",
            "quantity",
            "available_quantity",
            "is_available",
            "cover_image",
            "publication_year",
            "publisher",
            "date_added",
            "times_issued",
        ]
        read_only_fields = ["date_added"]

    def get_available_quantity(self, obj):
        return obj.available_quantity()

    def get_times_issued(self, obj):
        return obj.times_issued()

    def get_is_available(self, obj):
        return obj.is_available()


class BookDetailSerializer(BookSerializer):
    current_issues = serializers.SerializerMethodField()

    class Meta(BookSerializer.Meta):
        fields = BookSerializer.Meta.fields + ["current_issues"]

    def get_current_issues(self, obj):
        issues = IssuedBook.objects.filter(
            book=obj, returned_date__isnull=True
        ).select_related("student__user")

        return IssuedBookSerializer(
            issues, many=True, context=self.context
        ).data


class UserBasicSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]
        read_only_fields = ["id", "username"]


class StudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    full_name = serializers.SerializerMethodField()
    active_issues_count = serializers.SerializerMethodField()
    can_issue_more_books = serializers.SerializerMethodField()
    total_fines = serializers.SerializerMethodField()
    overdue_books_count = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "user",
            "username",
            "email",
            "full_name",
            "classroom",
            "branch",
            "roll_no",
            "phone",
            "image",
            "date_joined",
            "is_active",
            "active_issues_count",
            "can_issue_more_books",
            "total_fines",
            "overdue_books_count",
        ]
        read_only_fields = ["user", "date_joined"]

    def get_full_name(self, obj):
        return obj.full_name

    def get_active_issues_count(self, obj):
        return obj.active_issues_count()

    def get_can_issue_more_books(self, obj):
        return obj.can_issue_more_books()

    def get_total_fines(self, obj):
        return float(obj.total_fines())

    def get_overdue_books_count(self, obj):
        return obj.get_overdue_books().count()


class IssuedBookSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source="student.user.username", read_only=True
    )
    book_name = serializers.CharField(source="book.name", read_only=True)
    book_author = serializers.CharField(source="book.author", read_only=True)

    is_overdue = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()
    calculated_fine = serializers.SerializerMethodField()

    class Meta:
        model = IssuedBook
        fields = [
            "id",
            "student",
            "student_name",
            "book",
            "book_name",
            "book_author",
            "issued_date",
            "expiry_date",
            "returned_date",
            "fine_amount",
            "fine_paid",
            "is_overdue",
            "days_until_due",
            "calculated_fine",
        ]
        read_only_fields = ["issued_date", "expiry_date"]

    def get_is_overdue(self, obj):
        return obj.is_overdue()

    def get_days_until_due(self, obj):
        return obj.days_until_due()

    def get_calculated_fine(self, obj):
        return float(obj.calculate_fine())


class IssueBookSerializer(serializers.Serializer):
    book_id = serializers.IntegerField()
    student_id = serializers.IntegerField(required=False)

    def validate_book_id(self, value):
        try:
            book = Book.objects.get(id=value)
        except Book.DoesNotExist:
            raise serializers.ValidationError("Book not found.")

        if not book.is_available():
            raise serializers.ValidationError("Book is not available.")

        return value

    def validate_student_id(self, value):
        if value is None:
            return value

        try:
            student = Student.objects.get(id=value)
        except Student.DoesNotExist:
            raise serializers.ValidationError("Student not found.")

        if not student.is_active:
            raise serializers.ValidationError("Student account is inactive.")

        if student.get_overdue_books().exists():
            raise serializers.ValidationError(
                "Student has overdue books."
            )

        if not student.can_issue_more_books():
            raise serializers.ValidationError(
                f"Student reached maximum limit of {Student.MAX_BOOKS_ALLOWED} books."
            )

        return value


class ReturnBookSerializer(serializers.Serializer):
    issued_book_id = serializers.IntegerField()

    def validate_issued_book_id(self, value):
        try:
            issued_book = IssuedBook.objects.get(id=value)
        except IssuedBook.DoesNotExist:
            raise serializers.ValidationError(
                "Issued book record not found."
            )

        if issued_book.returned_date:
            raise serializers.ValidationError(
                "Book already returned."
            )

        return value


class ExtendIssueSerializer(serializers.Serializer):
    days = serializers.IntegerField(
        default=7,
        min_value=1,
        max_value=30
    )
