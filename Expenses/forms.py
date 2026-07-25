from django import forms
from .models import Transaction, Category

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['title', 'amount', 'category', 'date', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # Safely pop custom arguments if passed from views
        kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Explicitly pull all categories from the database into the dropdown
        self.fields['category'].queryset = Category.objects.all()
        self.fields['category'].empty_label = "Select a Category"