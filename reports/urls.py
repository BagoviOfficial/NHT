from django.urls import path
from . import views

urlpatterns = [
    path('statements/daily/', views.daily_statement_view, name='daily_statement'),
    path('statements/daily/pdf/', views.daily_statement_pdf_view, name='daily_statement_pdf'),
]
