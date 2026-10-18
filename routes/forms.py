from django import forms
from .models import Route


class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ['name', 'origin', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mandera'}),
            'origin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nairobi'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional stopover details'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
