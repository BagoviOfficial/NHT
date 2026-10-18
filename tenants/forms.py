from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from .models import Tenant, TenantPlan, TenantStatus

User = get_user_model()


class InstallClientForm(forms.Form):
    """
    Client Provisioning Form for the SaaS Master Dashboard.
    Collects company branding, system limits, and initial administrator credentials.
    """
    # Organization Info
    name = forms.CharField(
        label="Company / Enterprise Name",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'e.g. Tawakal Express Courier',
            'autocomplete': 'off'
        })
    )
    slug = forms.CharField(
        label="Tenant Slug / Subdomain",
        max_length=60,
        help_text="URL identifier, e.g. 'tawakal' -> /c/tawakal/ or tawakal.domain.com",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. tawakal',
            'autocomplete': 'off'
        })
    )
    tracking_prefix = forms.CharField(
        label="Consignment Tracking Prefix",
        max_length=10,
        help_text="2 to 10 uppercase letters used for tracking numbers (e.g. TWK-XXXXXXXX)",
        widget=forms.TextInput(attrs={
            'class': 'form-control text-uppercase',
            'placeholder': 'e.g. TWK',
            'autocomplete': 'off'
        })
    )
    head_office = forms.CharField(
        label="Head Office / Origin Hub",
        max_length=100,
        initial="Nairobi",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Nairobi Central Hub'
        })
    )
    currency = forms.CharField(
        label="Currency (ISO)",
        max_length=10,
        initial="KES",
        widget=forms.TextInput(attrs={
            'class': 'form-control text-uppercase',
            'placeholder': 'e.g. KES, USD'
        })
    )
    support_phone = forms.CharField(
        label="Customer Hotline",
        max_length=50,
        initial="+254 700 000000",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+254 7...'
        })
    )
    support_email = forms.EmailField(
        label="Support Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'support@client.co.ke'
        })
    )
    plan = forms.ChoiceField(
        label="Subscription Plan Tier",
        choices=TenantPlan.choices,
        initial=TenantPlan.PROFESSIONAL,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    primary_color = forms.CharField(
        label="Primary Brand Color",
        max_length=20,
        required=False,
        initial="#0d47a1",
        help_text="Primary color used for headers and primary buttons (e.g. #0d47a1)",
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color', 'title': 'Choose primary color'})
    )
    accent_color = forms.CharField(
        label="Accent / Highlight Color",
        max_length=20,
        required=False,
        initial="#ff8f00",
        help_text="Accent color used for highlights and badges (e.g. #ff8f00)",
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color', 'title': 'Choose accent color'})
    )

    # Initial Administrator Info
    admin_username = forms.CharField(
        label="Client Super Admin Username",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. tawakal_admin'
        })
    )
    admin_first_name = forms.CharField(
        label="Admin First Name",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Ahmed'})
    )
    admin_last_name = forms.CharField(
        label="Admin Last Name",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Hassan'})
    )
    admin_phone = forms.CharField(
        label="Admin Phone Number",
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 0712345678'
        })
    )
    admin_email = forms.EmailField(
        label="Admin Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'admin@client.co.ke'
        })
    )
    admin_password = forms.CharField(
        label="Initial Admin Password",
        required=False,
        help_text="Leave blank to automatically generate a cryptographically strong temporary password.",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave blank to auto-generate'
        })
    )

    # Starter Routes
    starter_routes = forms.CharField(
        label="Starter Destination Routes (Optional)",
        required=False,
        help_text="Comma-separated list of initial destination branches to provision automatically.",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'e.g. Garissa, Wajir, Mandera, Moyale, Isiolo'
        })
    )

    def clean_slug(self):
        slug = slugify(self.cleaned_data['slug'].strip())
        if not slug:
            raise ValidationError("Please provide a valid alphanumeric slug.")
        if Tenant.objects.filter(slug=slug).exists():
            raise ValidationError(f"A client with subdomain/slug '{slug}' is already registered.")
        return slug

    def clean_tracking_prefix(self):
        prefix = self.cleaned_data['tracking_prefix'].strip().upper()
        if not prefix.isalpha():
            raise ValidationError("Tracking prefix must contain letters only.")
        if len(prefix) < 2 or len(prefix) > 10:
            raise ValidationError("Tracking prefix must be between 2 and 10 characters.")
        if Tenant.objects.filter(tracking_prefix=prefix).exists():
            raise ValidationError(f"A client with tracking prefix '{prefix}' is already registered.")
        return prefix

    def clean_admin_username(self):
        username = self.cleaned_data['admin_username'].strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError(f"Username '{username}' is already in use by another account.")
        return username

    def clean_admin_phone(self):
        phone = self.cleaned_data['admin_phone'].strip()
        if User.objects.filter(phone=phone).exists():
            raise ValidationError(f"Phone number '{phone}' is already registered.")
        return phone

    def clean_primary_color(self):
        return self.cleaned_data.get('primary_color', '').strip() or '#0d47a1'

    def clean_accent_color(self):
        return self.cleaned_data.get('accent_color', '').strip() or '#ff8f00'


class TenantEditForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = [
            'name', 'head_office', 'currency', 'support_phone',
            'support_email', 'primary_color', 'accent_color',
            'plan', 'status', 'is_active',
            'receipt_header', 'receipt_footer',
            'allow_superuser_edit_after_dispatch',
            'tracking_rate_limit_per_minute',
            'max_users', 'max_routes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'head_office': forms.TextInput(attrs={'class': 'form-control'}),
            'currency': forms.TextInput(attrs={'class': 'form-control text-uppercase'}),
            'support_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'support_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color', 'title': 'Choose primary color'}),
            'accent_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color', 'title': 'Choose accent color'}),
            'plan': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receipt_header': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'receipt_footer': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'allow_superuser_edit_after_dispatch': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tracking_rate_limit_per_minute': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_users': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_routes': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class TenantAdminPasswordResetForm(forms.Form):
    new_password = forms.CharField(
        label="New Password for Client Admin",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new secure password'}),
        min_length=8
    )
