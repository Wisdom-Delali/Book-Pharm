from django import forms

from .codes import normalize_isbn
from .models import Book, StockAdjustment


class BookForm(forms.ModelForm):
    # Declared explicitly (not left to ModelForm's auto-generation) because
    # the model's isbn field is max_length=13 to store the canonical digit
    # form — but raw scanned/typed input ("978-0-13-468599-1") is longer than
    # that until normalize_isbn() strips it down. A max_length tied to the
    # model field would reject that raw input before normalization ever runs.
    isbn = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': 'Scan or leave blank if none'}),
        help_text='Leave blank if this title has no ISBN — an internal code is generated automatically.',
    )

    class Meta:
        model = Book
        fields = [
            'title', 'author', 'isbn', 'category', 'cost_price', 'selling_price',
            'stock_qty', 'low_stock_threshold', 'cover_image', 'description', 'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_isbn(self):
        raw = self.cleaned_data.get('isbn', '').strip()
        return normalize_isbn(raw) if raw else None


class StockAdjustmentForm(forms.Form):
    delta = forms.IntegerField(help_text='Positive to add stock, negative to remove.')
    reason = forms.ChoiceField(choices=StockAdjustment.Reason.choices)
    notes = forms.CharField(max_length=255, required=False)
