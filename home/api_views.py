from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import transaction
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Category, Book, Student, IssuedBook
from .serializers import (
    CategorySerializer, BookSerializer, BookDetailSerializer,
    StudentSerializer, IssuedBookSerializer, IssueBookSerializer,
    ReturnBookSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Category CRUD operations.
    List and retrieve are available to all authenticated users.
    Create, update, and delete are restricted to staff members.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """Staff-only for create, update, delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return super().get_permissions()


class BookViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Book CRUD operations.
    List and retrieve are available to all authenticated users.
    Create, update, and delete are restricted to staff members.
    """
    queryset = Book.objects.all().select_related('category')
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == 'retrieve':
            return BookDetailSerializer
        return BookSerializer
    
    def get_permissions(self):
        """Staff-only for create, update, delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return super().get_permissions()
    
    def get_queryset(self):
        """Filter books based on query parameters"""
        queryset = super().get_queryset()
        
        # Search by name, author, or ISBN
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(author__icontains=search) |
                models.Q(isbn__icontains=search)
            )
        
        # Filter by category
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category_id=category)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def available_books(self, request):
        """Get all books that have at least one copy available"""
        books = [book for book in self.get_queryset() if book.is_available()]
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='by-category/(?P<category_id>[^/.]+)')
    def by_category(self, request, category_id=None):
        """Get all books in a specific category"""
        books = self.get_queryset().filter(category_id=category_id)
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a book with safety checks"""
        book = self.get_object()
        
        # Check if book is currently issued
        issued_count = IssuedBook.objects.filter(
            book=book,
            returned_date__isnull=True
        ).count()
        
        if issued_count > 0:
            return Response(
                {
                    'error': f"Cannot delete '{book.name}'. {issued_count} copy(ies) currently issued. "
                             "Please wait for all copies to be returned."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)


class StudentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Student CRUD operations.
    Most operations are restricted to admin users.
    Students can view their own profile and issued books.
    """
    queryset = Student.objects.all().select_related('user')
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """Admin-only for most operations, except student-specific actions"""
        if self.action in ['my_profile', 'my_issued_books', 'my_overdue_books']:
            return [IsAuthenticated()]
        return [IsAdminUser()]
    
    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """Get current user's student profile"""
        try:
            student = request.user.student
            serializer = self.get_serializer(student)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response(
                {'error': 'You do not have a student profile.'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def my_issued_books(self, request):
        """Get current user's issued books"""
        try:
            student = request.user.student
            issued_books = IssuedBook.objects.filter(
                student=student,
                returned_date__isnull=True
            ).select_related('book')
            serializer = IssuedBookSerializer(issued_books, many=True)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response(
                {'error': 'You do not have a student profile.'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def my_overdue_books(self, request):
        """Get current user's overdue books"""
        try:
            student = request.user.student
            overdue_books = student.get_overdue_books()
            serializer = IssuedBookSerializer(overdue_books, many=True)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response(
                {'error': 'You do not have a student profile.'},
                status=status.HTTP_404_NOT_FOUND
            )


class IssuedBookViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for IssuedBook operations.
    Provides read-only access to issued books list.
    Custom actions for issuing and returning books.
    """
    queryset = IssuedBook.objects.all().select_related('book', 'student__user')
    serializer_class = IssuedBookSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def active_issues(self, request):
        """Get all currently issued books (not yet returned)"""
        active_books = self.get_queryset().filter(returned_date__isnull=True)
        serializer = self.get_serializer(active_books, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue_books(self, request):
        """Get all overdue books"""
        overdue = self.get_queryset().filter(
            returned_date__isnull=True,
            expiry_date__lt=timezone.now().date()
        )
        serializer = self.get_serializer(overdue, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def issue_book(self, request):
        """Issue a book to a student"""
        serializer = IssueBookSerializer(data=request.data)
        
        if serializer.is_valid():
            book_id = serializer.validated_data['book_id']
            student_id = serializer.validated_data.get('student_id')
            
            # If student_id not provided, use current user's student profile
            if not student_id:
                try:
                    student = request.user.student
                except Student.DoesNotExist:
                    return Response(
                        {'error': 'You do not have a student profile.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                student = get_object_or_404(Student, id=student_id)
            
            book = get_object_or_404(Book, id=book_id)
            
            try:
                with transaction.atomic():
                    # Create issued book record
                    issued_book = IssuedBook.objects.create(
                        student=student,
                        book=book
                    )
                    
                    result_serializer = IssuedBookSerializer(issued_book)
                    return Response(
                        {
                            'message': f"Book '{book.name}' issued successfully to {student.user.username}.",
                            'issued_book': result_serializer.data
                        },
                        status=status.HTTP_201_CREATED
                    )
            except Exception as e:
                return Response(
                    {'error': f'Error issuing book: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def return_book(self, request):
        """Return an issued book"""
        serializer = ReturnBookSerializer(data=request.data)
        
        if serializer.is_valid():
            issued_book_id = serializer.validated_data['issued_book_id']
            issued_book = get_object_or_404(IssuedBook, id=issued_book_id)
            
            try:
                with transaction.atomic():
                    # Mark as returned
                    issued_book.returned_date = timezone.now().date()
                    
                    # Calculate and store fine if overdue
                    if issued_book.is_overdue():
                        fine = issued_book.calculate_fine()
                        issued_book.fine_amount = fine
                        
                        issued_book.save()
                        
                        result_serializer = IssuedBookSerializer(issued_book)
                        return Response(
                            {
                                'message': f"Book '{issued_book.book.name}' returned successfully. "
                                          f"Fine: ${fine} (book was overdue).",
                                'issued_book': result_serializer.data,
                                'fine_amount': float(fine)
                            },
                            status=status.HTTP_200_OK
                        )
                    else:
                        issued_book.save()
                        
                        result_serializer = IssuedBookSerializer(issued_book)
                        return Response(
                            {
                                'message': f"Book '{issued_book.book.name}' returned successfully.",
                                'issued_book': result_serializer.data
                            },
                            status=status.HTTP_200_OK
                        )
            except Exception as e:
                return Response(
                    {'error': f'Error returning book: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
