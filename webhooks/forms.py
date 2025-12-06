from django import forms
from .models import Webhook

class WebhookForm(forms.ModelForm):
    events = forms.MultipleChoiceField(
        choices=Webhook.EVENT_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    class Meta:
        model = Webhook
        fields = ['url', 'events', 'is_active']
        widgets = {
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
