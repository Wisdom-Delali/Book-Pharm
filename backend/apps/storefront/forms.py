from django import forms

from apps.fulfillment.models import DeliveryPricingRule, Fulfillment
from apps.fulfillment.services import DistanceOutOfRange, distance_pricing_available, resolve_distance_fee


class CheckoutForm(forms.Form):
    customer_phone = forms.CharField(max_length=20, label='Phone number')
    customer_full_name = forms.CharField(max_length=150, required=False, label='Full name')
    # Optional everywhere else in the system (CLAUDE.md: "phone required,
    # rest optional-but-prompted") but Paystack's initialize call requires
    # an email — that's a payment-gateway constraint, not a Book Pharm
    # policy change, so it's required specifically on this form only.
    customer_email = forms.EmailField(label='Email (required to receive your payment receipt)')
    customer_birthday = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='Birthday')

    fulfillment_type = forms.ChoiceField(choices=Fulfillment.Type.choices, widget=forms.RadioSelect)
    # FIXED_ZONE fallback path — only actually required in clean() when
    # distance-based pricing isn't configured (see below).
    delivery_zone = forms.ModelChoiceField(
        queryset=DeliveryPricingRule.objects.filter(is_active=True, method=DeliveryPricingRule.Method.FIXED_ZONE),
        required=False, label='Delivery zone',
    )
    # Single-line, not Textarea: google.maps.places.Autocomplete attaches to
    # an HTMLInputElement specifically (checkout.html) — a full formatted
    # address reads fine on one line regardless.
    address = forms.CharField(
        max_length=255, required=False, widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label='Address / drop-off location',
    )
    # Hidden, filled by JS from the Places Autocomplete selection's
    # geometry.location or from device geolocation directly — only
    # meaningful, and only required, for DELIVERY when distance-based
    # pricing is configured (see clean()).
    latitude = forms.DecimalField(required=False, widget=forms.HiddenInput())
    longitude = forms.DecimalField(required=False, widget=forms.HiddenInput())

    def clean(self):
        cleaned = super().clean()
        ftype = cleaned.get('fulfillment_type')

        if ftype in (Fulfillment.Type.DELIVERY, Fulfillment.Type.RIDER_DELIVERY) and not cleaned.get('address'):
            self.add_error('address', 'Please provide an address.')

        if ftype == Fulfillment.Type.DELIVERY:
            if distance_pricing_available():
                lat, lng = cleaned.get('latitude'), cleaned.get('longitude')
                if lat is None or lng is None:
                    self.add_error(
                        'address',
                        'Please pick your address from the suggestions, or use "my current location", '
                        'so we can calculate your delivery fee.',
                    )
                else:
                    try:
                        resolve_distance_fee(lat, lng)
                    except DistanceOutOfRange:
                        self.add_error(
                            'address',
                            "Sorry, this address is outside our delivery range. Please choose Pickup or "
                            "Rider Delivery (Yango/Bolt/Uber) instead.",
                        )
            elif not cleaned.get('delivery_zone'):
                self.add_error('delivery_zone', 'Please select your delivery zone.')

        return cleaned
