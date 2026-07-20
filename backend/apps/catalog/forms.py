from django import forms

from .codes import normalize_isbn
from .models import Book, StockAdjustment, Tag


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

    # Freeform text, not a ModelMultipleChoiceField — tags are user-created
    # on the fly (unlike Category, a fixed, admin-managed list), so typing a
    # name that doesn't exist yet should just create it. See clean_tags()
    # and save() below; deliberately not in Meta.fields since it isn't a
    # real form-field-to-model-field mapping ModelForm can handle itself.
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. First Edition, Signed, Hardcover'}),
        help_text='Comma-separated. New tags are created automatically — different from Category, which is a fixed list.',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['tags'].initial = ', '.join(self.instance.tags.values_list('name', flat=True))

    def clean_isbn(self):
        raw = self.cleaned_data.get('isbn', '').strip()
        return normalize_isbn(raw) if raw else None

    def clean_tags(self):
        raw = self.cleaned_data.get('tags', '')
        # Case-insensitive de-dupe, keeping first-seen casing — "Signed" and
        # "signed" typed on two different books should end up as one tag.
        seen = {}
        for name in raw.split(','):
            name = name.strip()
            if name:
                seen.setdefault(name.lower(), name)
        return list(seen.values())

    def save(self, commit=True):
        book = super().save(commit=commit)
        tags = [Tag.objects.get_or_create(name=name)[0] for name in self.cleaned_data.get('tags', [])]
        book.tags.set(tags)
        return book


class StockAdjustmentForm(forms.Form):
    delta = forms.IntegerField(help_text='Positive to add stock, negative to remove.')
    reason = forms.ChoiceField(choices=StockAdjustment.Reason.choices)
    notes = forms.CharField(max_length=255, required=False)
