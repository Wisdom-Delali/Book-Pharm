from django import forms

from .models import DeliveryPricingRule, ShopLocation


class ShopLocationForm(forms.ModelForm):
    class Meta:
        model = ShopLocation
        fields = ['address', 'latitude', 'longitude']
        widgets = {
            # Filled by JS from the Places Autocomplete selection
            # (templates/portal/delivery/_content.html) — the address input
            # itself is what the owner interacts with.
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('address') and (cleaned.get('latitude') is None or cleaned.get('longitude') is None):
            self.add_error('address', 'Pick the address from the suggestions dropdown so it resolves to a map location.')
        return cleaned


class DeliveryPricingRuleForm(forms.ModelForm):
    class Meta:
        model = DeliveryPricingRule
        fields = ['method', 'zone_name', 'radius_km', 'fee', 'is_active']

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get('method')
        if method == DeliveryPricingRule.Method.FIXED_ZONE and not cleaned.get('zone_name'):
            self.add_error('zone_name', 'Zone name is required for a fixed-zone rule.')
        if method == DeliveryPricingRule.Method.DISTANCE_BASED and cleaned.get('radius_km') is None:
            self.add_error('radius_km', 'Radius (km) is required for a distance-based rule.')
        return cleaned
