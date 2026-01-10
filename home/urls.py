from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('add_book/', views.add_book, name='add_book'),
    path('edit_book/<int:book_id>/', views.edit_book, name='edit_book'),
    path('issue_book/', views.issue_book, name='issue_book'),
    path('return_book/', views.return_book, name='return_book'),
    path('issued_books/', views.view_issued_books, name='view_issued_books'),
    path('overdue_books/', views.view_overdue_books, name='overdue_books'),
    path('delete_book/<int:myid>/', views.delete_book, name='delete_book'),
    
    # Teacher & Subject Management
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/edit/<int:pk>/', views.edit_subject, name='edit_subject'),
    path('subjects/delete/<int:pk>/', views.delete_subject, name='delete_subject'),
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/add/', views.add_teacher, name='add_teacher'),
    path('teachers/edit/<int:pk>/', views.edit_teacher, name='edit_teacher'),
    path('teachers/delete/<int:pk>/', views.delete_teacher, name='delete_teacher'),
    path('student/qr/<int:student_id>/', views.student_qr_code, name='student_qr_code'),
    path('search_books_api/', views.search_books_api, name='search_books_api'),
]

