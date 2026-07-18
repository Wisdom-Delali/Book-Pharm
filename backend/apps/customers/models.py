from django.db import models

from .phone import normalize_phone


class Customer(models.Model):
    phone = models.CharField(max_length=13, unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['full_name', 'phone']

    def __str__(self):
        return self.full_name or self.phone

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)
