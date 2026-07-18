from django import forms

from .models import DiscountRule


class DiscountRuleForm(forms.ModelForm):
    class Meta:
        model = DiscountRule
        fields = ['name', 'discount_type', 'value', 'scope', 'category', 'book', 'approval_level', 'is_active']

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get('scope')
        if scope == DiscountRule.Scope.CATEGORY and not cleaned.get('category'):
            self.add_error('category', 'Required when scope is Category.')
        if scope == DiscountRule.Scope.BOOK and not cleaned.get('book'):
            self.add_error('book', 'Required when scope is Book.')
        discount_type = cleaned.get('discount_type')
        value = cleaned.get('value')
        if discount_type == DiscountRule.DiscountType.PERCENT and value is not None and not (0 < value <= 100):
            self.add_error('value', 'Percentage discounts must be greater than 0 and at most 100.')
        return cleaned
