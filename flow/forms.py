from django import forms
from .models import FlowTemplate, FormDef


class FlowTemplateForm(forms.ModelForm):
    class Meta:
        model = FlowTemplate
        fields = ["code", "name", "description", "form_def", "status", "version"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "form_def": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "version": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }


