from django import forms
from .models import AttendanceRecord

class AttendanceForm(forms.ModelForm):
    person_name = forms.CharField(label="人员姓名", max_length=100)

    class Meta:
        model = AttendanceRecord
        fields = [
            'type', 'person_name', 'start_date', 'duration',
            'leave_type', 'leave_reason',
            'overtime_reason', 'overtime_place'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'leave_reason': forms.Textarea(attrs={'rows': 3}),
            'overtime_reason': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_duration(self):
        duration = self.cleaned_data.get('duration')
        if duration is not None and duration <= 0:
            raise forms.ValidationError("时长必须大于0")
        return duration
