from django.urls import path
from . import views

urlpatterns = [

    # Home
    path('', views.index, name='home'),

    # -----------------------
    # Book Management
    # -----------------------
    path('books/', views.index, name='book_list'),
    path('books/add/', views.add_book, name='book_add'),
    path('books/<int:book_id>/', views.book_detail, name='book_detail'),
    path('books/<int:book_id>/edit/', views.edit_book, name='book_edit'),
    path('books/<int:book_id>/delete/', views.delete_book, name='book_delete'),

    # -----------------------
    # Book Issue & Return
    # -----------------------
    path('books/issue/', views.issue_book, name='book_issue'),
    path('books/return/', views.return_book, name='book_return'),
    path('books/issued/', views.view_issued_books, name='issued_books'),
    path('books/overdue/', views.view_overdue_books, name='overdue_books'),

    # -----------------------
    # Library Statistics
    # -----------------------
    path('statistics/', views.library_statistics, name='library_statistics'),

    # -----------------------
    # Subject Management
    # -----------------------
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/<int:pk>/edit/', views.edit_subject, name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.delete_subject, name='subject_delete'),

    # -----------------------
    # Teacher Management
    # -----------------------
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/add/', views.add_teacher, name='teacher_add'),
    path('teachers/<int:pk>/edit/', views.edit_teacher, name='teacher_edit'),
    path('teachers/<int:pk>/delete/', views.delete_teacher, name='teacher_delete'),

    # -----------------------
    # Student Management
    # -----------------------
    path('students/<int:student_id>/', views.student_detail, name='student_detail'),
    path('students/<int:student_id>/qr/', views.student_qr_code, name='student_qr'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),

    # -----------------------
    # API Endpoints
    # -----------------------
    path('api/books/search/', views.search_books_api, name='search_books_api'),

    # -----------------------
    # Fine Payment
    # -----------------------
    path('fines/pay/<int:issued_book_id>/', views.pay_fine, name='pay_fine'),

]
