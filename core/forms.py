from django import forms
from .models import SiteSettings, FieldConfig, ChoiceConfig, ALLOWED_FIELD_KEYS, ALLOWED_CHOICE_CATEGORIES


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            'company_name', 'currency', 'head_office',
            'support_phone', 'support_email',
            'receipt_header', 'receipt_footer',
            'about_text', 'help_text',
            'allow_superuser_edit_after_dispatch',
            'tracking_rate_limit_per_minute'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'head_office': forms.TextInput(attrs={'class': 'form-control'}),
            'support_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'support_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'receipt_header': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'receipt_footer': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'about_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'help_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'allow_superuser_edit_after_dispatch': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tracking_rate_limit_per_minute': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class FieldConfigForm(forms.ModelForm):
    class Meta:
        model = FieldConfig
        fields = ['label', 'placeholder', 'help_text', 'is_required', 'is_visible', 'order', 'is_active']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control'}),
            'placeholder': forms.TextInput(attrs={'class': 'form-control'}),
            'help_text': forms.TextInput(attrs={'class': 'form-control'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_visible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ChoiceConfigForm(forms.ModelForm):
    class Meta:
        model = ChoiceConfig
        fields = ['category', 'key', 'label', 'is_default', 'is_active', 'order']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'key': forms.TextInput(attrs={'class': 'form-control'}),
            'label': forms.TextInput(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        key = (cleaned_data.get('key') or '').strip()
        tenant = self.tenant or (self.instance.tenant if self.instance and self.instance.pk else None)
        if category and key:
            qs = ChoiceConfig.objects.filter(tenant=tenant, category=category, key=key)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('key', f"A choice with key '{key}' already exists in this category.")
        return cleaned_data
