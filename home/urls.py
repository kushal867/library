from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('add_book/', views.add_book, name='add_book'),
    path('edit_book/<int:book_id>/', views.edit_book, name='edit_book'),
    path('issue_book/', views.issue_book, name='issue_book'),
    path('return_book/', views.return_book, name='return_book'),
    path('issued_books/', views.view_issued_books, name='view_issued_books'),
    path('overdue_books/', views.view_overdue_books, name='view_overdue_books'),
    path('delete_book/<int:myid>/', views.delete_book, name='delete_book'),
]