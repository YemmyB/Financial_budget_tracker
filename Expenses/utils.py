import re
from datetime import datetime
from .models import Category, Transaction

# Define your keyword rules mapping keywords to category names
CATEGORY_RULES = {
    'Food & Groceries': ['naivas', 'quickmart', 'carrefour', 'chandarana', 'tuskys'],
    'Utilities': ['kplc', 'token', 'nairobi water', 'zuku', 'safaricom home', 'faiba'],
    'Transportation': ['uber', 'bolt', 'total', 'shell', 'rubis'],
    'Airtime & Data': ['airtime', 'data bundle', 'safaricom data'],
}

def match_category_by_keyword(text):
    """
    Scans the transaction text for keywords and returns the matching Category object.
    """
    text_lower = text.lower()
    
    for category_name, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            if keyword in text_lower:
                category, _ = Category.objects.get_or_create(
                    name=category_name, 
                    defaults={'is_income': False}
                )
                return category
                
    # Fallback default category if no keyword matches
    default_cat, _ = Category.objects.get_or_create(
        name='Uncategorized', 
        defaults={'is_income': False}
    )
    return default_cat

def parse_mpesa_sms(sms_text, user):
    """
    Parses an incoming M-Pesa SMS string, applies automated category rules, 
    and saves a Transaction to the database.
    """
    sms_text = sms_text.strip()
    
    pay_match = re.search(r'([A-Z0-9]+)\s+Confirmed\.?\s+(?:Ksh|KES)\s*([\d,]+\.\d{2})\s+paid to\s+([A-Z0-9\s\*]+?)\s+on', sms_text, re.IGNORECASE)
    
    if pay_match:
        trans_id, amount_str, recipient = pay_match.groups()
        amount = float(amount_str.replace(',', ''))
        recipient_clean = recipient.strip()
        
        # Automatically assign category based on text keywords
        full_text_to_check = f"{sms_text} {recipient_clean}"
        category = match_category_by_keyword(full_text_to_check)
        
        Transaction.objects.create(
            user=user,
            title=f"Paid to {recipient_clean}",
            amount=amount,
            category=category,
            date=datetime.today().date(),
            description=f"Auto-logged from SMS: {sms_text}"
        )
        return True, f"Successfully logged and categorized as '{category.name}'!"

    return False, "Could not parse SMS format."