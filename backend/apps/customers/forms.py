from django import forms

from .models import LoyaltyProgram


class LoyaltyProgramForm(forms.ModelForm):
    class Meta:
        model = LoyaltyProgram
        fields = ['points_per_ghs', 'point_value_ghs', 'min_redeem_points', 'is_active']
