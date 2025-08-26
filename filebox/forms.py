from django import forms
from .models import UploadedFile, FileCategory

class UploadForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=FileCategory.objects.all(),
        required=False,
        label="所属分类",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = UploadedFile
        fields = ['title', 'description', 'file', 'category']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
