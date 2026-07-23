import re
from datetime import datetime
from .models import Category, Transaction

def parse_mpesa_sms(sms_text, user):
    """
    Parses an incoming M-Pesa SMS string, extracts details, 
    and saves a Transaction to the database for the given user.
    """
    # Clean up whitespace
    sms_text = sms_text.strip()

    # Match standard payment pattern: e.g., "QA45G7H8 Confirmed. Ksh4,500.00 paid to NAIVAS SUPERMARKET on 23/7/26"
    pay_match = re.search(r'([A-Z0-9]+)\s+Confirmed\.?\s+(?:Ksh|KES)\s*([\d,]+\.\d{2})\s+paid to\s+([A-Z0-9\s\*]+?)\s+on', sms_text, re.IGNORECASE)
    
    if pay_match:
        trans_id, amount_str, recipient = pay_match.groups()
        amount = float(amount_str.replace(',', ''))
        
        # Default fallback category for expenses
        category, _ = Category.objects.get_or_create(name='M-Pesa Expense', defaults={'is_income': False})
        
        Transaction.objects.create(
            user=user,
            title=f"Paid to {recipient.strip()}",
            amount=amount,
            category=category,
            date=datetime.today().date(),
            description=f"Auto-logged from SMS: {sms_text}"
        )
        return True, f"Successfully logged expense of {amount} to {recipient.strip()}"

    return False, "Could not parse SMS format."