from django.urls import path
from . import views


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('add/', views.add_expense, name='add_expense'),
    path('edit/<int:transaction_id>/', views.edit_expense, name='edit_expense'),
    path('delete/<int:transaction_id>/', views.delete_transaction, name='delete_transaction'),
    path('register/', views.register, name='register'),
    # Add the webhook URL:
    path('api/mpesa-sync/', views.mpesa_webhook, name='mpesa_webhook'),
    path('sync-sms/', views.manual_sms_sync, name='manual_sms_sync'),
    path('api/mpesa-sync/', views.api_mpesa_sync, name='api_mpesa_sync'),
]