import datetime
import re
from datetime import date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny # We use AllowAny because Tasker won't have a Django session
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from .models import Transaction, Category
from .forms import TransactionForm

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
def redirect():
    raise NotImplementedError

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
    context = {
        'transaction': transaction,
    }
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
#To determine the current month and year, we can use the datetime module. We can also allow users to filter transactions by month using a query parameter in the URL. If a month is selected, we will parse it and use it to filter the transactions. If no month is selected, we will default to the current month.
    today = datetime.date.today()
    year = today.year
    month = today.month
#To allow users to filter transactions by month, we can check if a 'month' query parameter is present in the request. If it is, we will parse it and use it to filter the transactions. If not, we will default to the current month.
    selected_month = request.GET.get('month')
    if selected_month:
        try:
            year_str, month_str = selected_month.split('-')
            year = int(year_str)
            month = int(month_str)
        except ValueError:
            pass
    #To ensure that the month is always in the format YYYY-MM, we can use an f-string to format the year and month as a string with leading zeros for the month if necessary.
    current_month_value = f"{year}-{month:02d}"
#To retrieve the transactions for the current user and the selected month, we can use the Django ORM to filter the Transaction model by user and date. We will also order the transactions by date in descending order.
    transactions = Transaction.objects.filter(
        user=request.user,
        date__year=year,
        date__month=month
        ).order_by('-date')
    total_income = (
        transactions.filter(category__is_income=True).aggregate(Sum('amount'))['amount__sum'] or 0)
    total_expense_by_category = (
        transactions.filter(category__is_income=False)
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    total_expense = sum(item['total'] for item in total_expense_by_category)
    balance = total_income - total_expense

    #Extract labels and values for the chart from the expense breakdown queryset. We will use a list comprehension to extract the category names and total amounts from the queryset and store them in separate lists.
    chart_labels = [item['category__name'] for item in total_expense_by_category]
    chart_data = [float(item['total']) for item in total_expense_by_category]

    context = {
        'form': form,
        'transactions': transactions,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }
    return render(request, 'expenses/dashboard.html', context)

@api_view(['POST'])
@permission_classes([AllowAny])
def mpesa_webhook(request):
    # 1. Get the raw text from the POST request body
    sms_text = request.data.get('sms', '')
    
    # We need a user to assign the transaction to. 
    # For a personal app, we can just grab the first admin user.
    user = User.objects.first()
    
    if not sms_text or not user:
        return Response({"error": "No SMS text provided or no user exists."}, status=400)

    # 2. Use Regex to extract Safaricom transaction data
    # Example SMS: "QA45G7H8 paid to NAIVAS SUPERMARKET Ksh 4,500.00 on 23/07/26 at 3:14 PM..."
    
    # Look for "Ksh" followed by an optional space, numbers, and commas
    amount_match = re.search(r'Ksh\s*([\d,]+(?:\.\d{2})?)', sms_text)
    
    # Determine transaction type and title based on Safaricom keywords
    if "paid to" in sms_text or "bought airtime" in sms_text:
        is_expense = True
        # Extract who it was paid to
        title_match = re.search(r'paid to (.*?) Ksh', sms_text)
        title = title_match.group(1).strip() if title_match else "M-Pesa Expense"
        
    elif "received Ksh" in sms_text:
        is_expense = False
        title_match = re.search(r'from (.*?) on', sms_text)
        title = title_match.group(1).strip() if title_match else "M-Pesa Income"
        
    else:
        # If the regex fails to match a known pattern, log it as unknown but save the text
        is_expense = True
        title = "Unknown M-Pesa Trx"

    # 3. Clean up the extracted data
    amount = 0.00
    if amount_match:
        # Remove commas from the amount (e.g. 4,500.00 -> 4500.00)
        amount_str = amount_match.group(1).replace(',', '')
        amount = float(amount_str)

    # 4. Find or create a default category so the database doesn't crash
    category_name = "M-Pesa"
    category, created = Category.objects.get_or_create(
        name=category_name, 
        defaults={'is_income': not is_expense}
    )

    # 5. Save the transaction to the database
    Transaction.objects.create(
        user=user,
        title=title,
        amount=amount,
        category=category,
        date=date.today()
    )

    return Response({"status": "Success", "title": title, "amount": amount}, status=201)