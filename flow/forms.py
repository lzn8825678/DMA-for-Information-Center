from django import forms
from .models import FlowTemplate, FormSchema


class FlowTemplateForm(forms.ModelForm):
    class Meta:
        model = FlowTemplate
        fields = ["code", "name", "description", "form", "status", "version"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "form": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "version": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }


class FormSchemaForm(forms.ModelForm):
    class Meta:
        model = FormSchema
        fields = ["name", "description", "json_schema", "ui_schema"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "json_schema": forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 10}),
            "ui_schema": forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 6}),
        }
