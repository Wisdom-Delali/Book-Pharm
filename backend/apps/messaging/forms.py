from django import forms

from .models import SmsCampaign


class SmsCampaignForm(forms.ModelForm):
    class Meta:
        model = SmsCampaign
        fields = ['name', 'audience', 'message', 'scheduled_for']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4, 'maxlength': 459}),
            'scheduled_for': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
