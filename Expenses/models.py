from django.db import models
from django.contrib.auth.models import User
class Category(models.Model):
    name = models.CharField(max_length=100)
    is_income = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Categories"


    def __str__(self):
        return self.name


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    date = models.DateField()

    notes = models.TextField(blank=True, null=True)
    is_favorite = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} - ${self.amount}"


