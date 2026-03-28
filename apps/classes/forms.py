from django import forms
from django.forms import formset_factory


DAY_CHOICES = [
    (0, "จันทร์"),
    (1, "อังคาร"),
    (2, "พุธ"),
    (3, "พฤหัสบดี"),
    (4, "ศุกร์"),
    (5, "เสาร์"),
    (6, "อาทิตย์"),
]


class DaySlotForm(forms.Form):
    day_of_week = forms.ChoiceField(
        choices=DAY_CHOICES,
        label="วันในสัปดาห์",
        widget=forms.Select(attrs={"class": "vSelect"}),
    )
    start_time = forms.TimeField(
        label="เวลาเริ่มต้น",
        widget=forms.TimeInput(attrs={"type": "time", "class": "vTimeField"}),
    )
    end_time = forms.TimeField(
        label="เวลาสิ้นสุด",
        widget=forms.TimeInput(attrs={"type": "time", "class": "vTimeField"}),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end <= start:
            raise forms.ValidationError("เวลาสิ้นสุดต้องมากกว่าเวลาเริ่มต้น")
        return cleaned


DaySlotFormSet = formset_factory(DaySlotForm, extra=0, min_num=1, validate_min=True)


class AutoCreateSessionsForm(forms.Form):
    start_date = forms.DateField(
        label="วันที่เริ่มต้น",
        widget=forms.DateInput(attrs={"type": "date", "class": "vDateField"}),
    )
    end_date = forms.DateField(
        label="วันที่สิ้นสุด",
        widget=forms.DateInput(attrs={"type": "date", "class": "vDateField"}),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("วันที่สิ้นสุดต้องไม่น้อยกว่าวันที่เริ่มต้น")
        return cleaned
