import re
from datetime import datetime
from .models import Transaction, Category

def parse_mpesa_sms(bulk_text, user):
    # Split the pasted text by lines to handle multiple SMS messages at once
    lines = bulk_text.strip().split('\n')
    
    success_count = 0
    
    for text in lines:
        text = text.strip()
        # Skip empty lines or lines that don't contain "Ksh" (non-M-Pesa text)
        if not text or "Ksh" not in text:
            continue
            
        try:
            # 1. Extract Amount (Handles formats like Ksh4,500.00 or Ksh 4,500)
            amount_match = re.search(r'Ksh\s*([\d,]+(?:\.\d{2})?)', text)
            if not amount_match:
                continue
            amount = float(amount_match.group(1).replace(',', ''))
            
            # 2. Extract Date (Handles formats like on 23/7/26 or 23/07/2026)
            date_match = re.search(r'on\s+(\d{1,2}/\d{1,2}/\d{2,4})', text)
            if date_match:
                date_str = date_match.group(1)
                try:
                    dt = datetime.strptime(date_str, '%d/%m/%y').date()
                except ValueError:
                    try:
                        dt = datetime.strptime(date_str, '%d/%m/%Y').date()
                    except ValueError:
                        dt = datetime.today().date()
            else:
                dt = datetime.today().date()
            
            # 3. Determine Transaction Type and Title based on keywords
            is_expense = True
            title = "Unknown M-Pesa Trx"
            
            if "paid to" in text:
                is_expense = True
                match = re.search(r'paid to (.*?) on', text)
                title = match.group(1).strip() if match else "M-Pesa Payment"
            elif "bought Ksh" in text and "airtime" in text:
                is_expense = True
                title = "Airtime Purchase"
            elif "sent to" in text:
                is_expense = True
                match = re.search(r'sent to (.*?) on', text)
                if not match:
                    match = re.search(r'sent to (.*?) for', text)
                title = match.group(1).strip() if match else "M-Pesa Sent"
            elif "received Ksh" in text:
                is_expense = False
                match = re.search(r'from (.*?) on', text)
                title = match.group(1).strip() if match else "M-Pesa Income"
            elif "Withdraw" in text or "withdrawn" in text.lower():
                is_expense = True
                match = re.search(r'from (.*?) on', text)
                title = match.group(1).strip() if match else "M-Pesa Withdrawal"

            # 4. Save to Database
            category_name = "M-Pesa"
            category, _ = Category.objects.get_or_create(
                name=category_name, 
                defaults={'is_income': not is_expense}
            )
            
            Transaction.objects.create(
                user=user,
                title=title[:100],
                amount=amount,
                category=category,
                date=dt,
                description=text[:255] # Saves the exact SMS text into the DB 
            )
            success_count += 1
            
        except Exception as e:
            # If one specific message line is corrupted, skip it and continue parsing the rest
            continue

    # Return success response to the view
    if success_count > 0:
        return True, f"Successfully logged {success_count} transaction(s)."
    else:
        return False, "Could not parse SMS format. Ensure the text contains valid M-Pesa messages."