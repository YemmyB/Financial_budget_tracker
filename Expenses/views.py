import datetime
import re
from datetime import date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import Transaction, Category
from .forms import TransactionForm
from django.http import JsonResponse, HttpResponse
import json
from .utils import parse_mpesa_sms
import os
import csv

@login_required
def manual_sms_sync(request):
    """View providing a web dashboard input box to paste and sync M-Pesa SMS strings."""
    message = None
    if request.method == 'POST':
        sms_text = request.POST.get('sms_text', '')
        success, message = parse_mpesa_sms(sms_text, request.user)
        if success:
            return redirect('dashboard')
            
    return render(request, 'expenses/manual_sync.html', {'message': message})

@csrf_exempt
def api_mpesa_sync(request):
    """API Endpoint for external webhooks."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            sms_text = data.get('sms', '')
            user = User.objects.first() 
            
            success, msg = parse_mpesa_sms(sms_text, user)
            if success:
                return JsonResponse({'status': 'success', 'message': msg}, status=200)
            return JsonResponse({'status': 'error', 'message': msg}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'error': 'Invalid method'}, status=405)

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'expenses/register.html', {'form': form})

@login_required
def add_expense(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            return redirect('dashboard')
    else:
        form = TransactionForm(user=request.user)

    context = {
        'form': form,
    }
    return render(request, 'expenses/add_expense.html', context)

def edit_expense(request, transaction_id):
    transaction = Transaction.objects.get(id=transaction_id, user=request.user)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = TransactionForm(instance=transaction, user=request.user)

    context = {
        'form': form,
        'transaction': transaction,
    }
    return render(request, 'expenses/edit_expense.html', context)

def delete_transaction(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    if request.method == 'POST':
        transaction.delete()
        return redirect('dashboard')
    return render(request, 'expenses/delete_expense.html', {'transaction': transaction})

@login_required
def dashboard(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            return redirect('dashboard')
    else:
        form = TransactionForm()

    today = datetime.date.today()
    year = today.year
    month = today.month

    selected_month = request.GET.get('month')
    if selected_month:
        try:
            year_str, month_str = selected_month.split('-')
            year = int(year_str)
            month = int(month_str)
        except ValueError:
            pass

    current_month_value = f"{year}-{month:02d}"

    transactions = Transaction.objects.filter(
        user=request.user,
        date__year=year,
        date__month=month
    ).order_by('-date')

    # Fetch all categories for the dashboard inline dropdown selection table
    categories = Category.objects.all()

    total_income = (
        transactions.filter(category__is_income=True).aggregate(Sum('amount'))['amount__sum'] or 0
    )
    
    total_expense_by_category = (
        transactions.filter(category__is_income=False)
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    
    total_expense = sum(item['total'] for item in total_expense_by_category)
    balance = total_income - total_expense

    # Extract labels and values for the Chart.js doughnut chart
    chart_labels = [item['category__name'] for item in total_expense_by_category]
    chart_data = [float(item['total']) for item in total_expense_by_category]

    context = {
        'form': form,
        'transactions': transactions,
        'categories': categories,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'current_month_value': current_month_value,
    }
    return render(request, 'expenses/dashboard.html', context)

def export_transactions_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Title', 'Amount', 'Category', 'Date', 'Description'])
    
    transactions = Transaction.objects.filter(user=request.user).select_related('category')
    for t in transactions:
        writer.writerow([
            t.id, 
            t.title, 
            t.amount, 
            t.category.name if t.category else '', 
            t.date, 
            t.description
        ])
    return response

@login_required
def upload_mpesa_statement(request):
    if request.method == 'POST' and request.FILES.get('statement_file'):
        csv_file = request.FILES['statement_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.reader(decoded_file)
        
        default_cat, _ = Category.objects.get_or_create(name='Uncategorized')
        
        for row in reader:
            try:
                date_str = row[0]
                details = row[1]
                withdrawn = row[3] if row[3] else 0.0
                paid_in = row[2] if row[2] else 0.0
                
                amount = float(str(withdrawn).replace(',', '')) if float(str(withdrawn or 0).replace(',', '')) > 0 else float(str(paid_in or 0).replace(',', ''))
                
                Transaction.objects.get_or_create(
                    user=request.user,
                    title=details[:100],
                    amount=amount,
                    date=datetime.datetime.strptime(date_str.split()[0], '%Y-%m-%d').date(),
                    defaults={'category': default_cat, 'description': details}
                )
            except (ValueError, IndexError):
                continue
                
        return redirect('dashboard')
        
    return render(request, 'expenses/upload_statement.html')

@login_required
def update_transaction_category(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    if request.method == 'POST':
        category_id = request.POST.get('category')
        if category_id:
            transaction.category_id = category_id
            transaction.save()
    return redirect('dashboard')

@api_view(['POST'])
@permission_classes([AllowAny])
def mpesa_webhook(request):
    sms_text = request.data.get('sms', '')
    user = User.objects.first()
    
    if not sms_text or not user:
        return Response({"error": "No SMS text provided or no user exists."}, status=400)

    amount_match = re.search(r'Ksh\s*([\d,]+(?:\.\d{2})?)', sms_text)
    
    if "paid to" in sms_text or "bought airtime" in sms_text:
        is_expense = True
        title_match = re.search(r'paid to (.*?) Ksh', sms_text)
        title = title_match.group(1).strip() if title_match else "M-Pesa Expense"
    elif "received Ksh" in sms_text:
        is_expense = False
        title_match = re.search(r'from (.*?) on', sms_text)
        title = title_match.group(1).strip() if title_match else "M-Pesa Income"
    else:
        is_expense = True
        title = "Unknown M-Pesa Trx"

    amount = 0.00
    if amount_match:
        amount_str = amount_match.group(1).replace(',', '')
        amount = float(amount_str)

    category_name = "M-Pesa"
    category, created = Category.objects.get_or_create(
        name=category_name, 
        defaults={'is_income': not is_expense}
    )

    Transaction.objects.create(
        user=user,
        title=title,
        amount=amount,
        category=category,
        date=date.today()
    )

    return Response({"status": "Success", "title": title, "amount": amount}, status=201)