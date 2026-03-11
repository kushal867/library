from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from django.db import transaction
from django.db.models import Q, Count, F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Category, Book, Student, IssuedBook
from .serializers import (
    CategorySerializer,
    BookSerializer,
    BookDetailSerializer,
    StudentSerializer,
    IssuedBookSerializer,
    IssueBookSerializer,
    ReturnBookSerializer,
    ExtendIssueSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return super().get_permissions()


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("category")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BookDetailSerializer
        return BookSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get("search")
        category = self.request.query_params.get("category")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(author__icontains=search)
                | Q(isbn__icontains=search)
            )

        if category:
            queryset = queryset.filter(category_id=category)

        return queryset

    @action(detail=False, methods=["get"])
    def available(self, request):
        books = self.get_queryset().annotate(
            issued_count=Count(
                "issues", filter=Q(issues__returned_date__isnull=True)
            )
        ).filter(quantity__gt=F("issued_count"))

        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        category_id = request.query_params.get("category_id")

        books = self.get_queryset().filter(category_id=category_id)

        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        book = self.get_object()

        issued_count = IssuedBook.objects.filter(
            book=book, returned_date__isnull=True
        ).count()

        if issued_count > 0:
            return Response(
                {
                    "error": "Cannot delete this book while copies are issued."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related("user")
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ["my_profile", "my_issued_books", "my_overdue_books"]:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def _get_student(self, user):
        try:
            return user.student
        except Student.DoesNotExist:
            return None

    @action(detail=False, methods=["get"])
    def my_profile(self, request):
        student = self._get_student(request.user)

        if not student:
            return Response(
                {"error": "Student profile not found"}, status=404
            )

        serializer = self.get_serializer(student)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_issued_books(self, request):
        student = self._get_student(request.user)

        if not student:
            return Response(
                {"error": "Student profile not found"}, status=404
            )

        books = IssuedBook.objects.filter(
            student=student, returned_date__isnull=True
        ).select_related("book")

        serializer = IssuedBookSerializer(books, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_overdue_books(self, request):
        student = self._get_student(request.user)

        if not student:
            return Response(
                {"error": "Student profile not found"}, status=404
            )

        books = student.get_overdue_books()

        serializer = IssuedBookSerializer(books, many=True)
        return Response(serializer.data)


class IssuedBookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IssuedBook.objects.select_related("book", "student__user")
    serializer_class = IssuedBookSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def active(self, request):
        books = self.get_queryset().filter(returned_date__isnull=True)

        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        books = self.get_queryset().filter(
            returned_date__isnull=True,
            expiry_date__lt=timezone.now().date(),
        )

        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def extend(self, request, pk=None):
        issued_book = self.get_object()

        serializer = ExtendIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        days = serializer.validated_data.get("days", 7)

        success, message = issued_book.extend_issue(days)

        if not success:
            return Response({"error": message}, status=400)

        return Response(
            {
                "message": message,
                "new_expiry_date": issued_book.expiry_date,
            }
        )

    @action(detail=False, methods=["post"])
    def issue(self, request):
        serializer = IssueBookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        book = get_object_or_404(
            Book, id=serializer.validated_data["book_id"]
        )

        student_id = serializer.validated_data.get("student_id")

        if student_id:
            student = get_object_or_404(Student, id=student_id)
        else:
            try:
                student = request.user.student
            except Student.DoesNotExist:
                return Response(
                    {"error": "Student profile not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if not student.can_issue_more_books():
            return Response(
                {"error": "Student cannot issue more books"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not book.is_available():
            return Response(
                {"error": "Book not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            issued_book = IssuedBook.objects.create(
                student=student,
                book=book,
            )

        result = IssuedBookSerializer(issued_book)

        return Response(
            {
                "message": "Book issued successfully",
                "issued_book": result.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    def return_book(self, request):
        serializer = ReturnBookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        issued = get_object_or_404(
            IssuedBook,
            id=serializer.validated_data["issued_book_id"],
        )

        with transaction.atomic():
            issued.returned_date = timezone.now().date()

            if issued.is_overdue():
                issued.fine_amount = issued.calculate_fine()

            issued.save()

        return Response(
            {
                "message": "Book returned successfully",
                "fine_amount": issued.fine_amount,
            }
        )
