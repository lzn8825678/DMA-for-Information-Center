from django import forms
from .models import RelicLocation

class RelicLocationForm(forms.ModelForm):
    class Meta:
        model = RelicLocation
        fields = ['country', 'region', 'institution', 'count', 'digitized_percent', 'publication', 'source']
        widgets = {
            'publication': forms.Textarea(attrs={'rows': 2}),
            'source': forms.Textarea(attrs={'rows': 2}),
        }
