from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from tenants.models import TenantPlan, Tenant


class WordPressStyleInstallForm(forms.Form):
    """
    The famous WordPress-style 1-Screen Setup Form.
    Configures Global Platform settings, Super Admin account, and the First Client Organization.
    """
    # ==========================
    # 1. Platform Settings
    # ==========================
    platform_title = forms.CharField(
        label="Platform Title / Installation Name",
        max_length=150,
        initial="Northern Highways Transporters — Cloud PMS",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'e.g. Northern Highways Transporters PMS'
        })
    )

    # ==========================
    # 2. Platform Owner Account
    # ==========================
    admin_username = forms.CharField(
        label="Global Super Admin Username",
        max_length=150,
        initial="platform_admin",
        help_text="Usernames can have letters, numbers, and @/./+/-/_ characters.",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. platform_admin'})
    )
    admin_password = forms.CharField(
        label="Super Admin Password",
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 8 characters (letters, numbers, symbols)'
        })
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Re-type your password'
        })
    )
    admin_phone = forms.CharField(
        label="Super Admin Phone Number",
        max_length=30,
        initial="0700000001",
        help_text="Required for SMS notifications & verification.",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0700000001'})
    )
    admin_email = forms.EmailField(
        label="Super Admin Email Address",
        initial="admin@northernhighways.co.ke",
        help_text="Double-check your email address before continuing.",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'admin@example.com'})
    )

    # ==========================
    # 3. Primary Client Company
    # ==========================
    company_name = forms.CharField(
        label="Primary Courier / Enterprise Name",
        max_length=150,
        initial="Northern Highways Transporters",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'e.g. Northern Highways Transporters'})
    )
    tracking_prefix = forms.CharField(
        label="Tracking Number Prefix",
        max_length=10,
        initial="NHT",
        help_text="Prefix used on receipts and consignments (e.g. NHT -> NHT-XXXXXXXX)",
        widget=forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. NHT'})
    )
    slug = forms.CharField(
        label="URL Slug / Subdomain Identifier",
        max_length=60,
        initial="nht",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. nht'})
    )
    head_office = forms.CharField(
        label="Central Origin Terminal Hub",
        max_length=100,
        initial="Nairobi",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nairobi'})
    )
    currency = forms.CharField(
        label="Operating Currency (ISO)",
        max_length=10,
        initial="KES",
        widget=forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'KES'})
    )
    primary_color = forms.CharField(
        label="Primary Brand Color",
        max_length=20,
        initial="#0d47a1",
        required=False,
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'})
    )
    accent_color = forms.CharField(
        label="Accent / Highlight Color",
        max_length=20,
        initial="#ff8f00",
        required=False,
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'})
    )
    starter_routes = forms.CharField(
        label="Starter Destination Routes",
        required=False,
        initial="Garissa, Wajir, Kotulo Drop-off, Elwak, Rhamu, Lafey, Arabia, Mandera",
        help_text="Comma-separated branches to seed immediately into the dispatch network.",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('admin_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")

        prefix = cleaned_data.get('tracking_prefix', '').strip().upper()
        if prefix:
            if not prefix.isalpha():
                self.add_error('tracking_prefix', "Tracking prefix must contain letters only.")
            elif len(prefix) < 2 or len(prefix) > 10:
                self.add_error('tracking_prefix', "Prefix must be between 2 and 10 characters.")
            else:
                try:
                    if Tenant.objects.filter(tracking_prefix=prefix).exists():
                        self.add_error('tracking_prefix', f"A tenant with tracking prefix '{prefix}' already exists.")
                except Exception:
                    pass
            cleaned_data['tracking_prefix'] = prefix

        slug = cleaned_data.get('slug', '').strip()
        if not slug and cleaned_data.get('company_name'):
            slug = slugify(cleaned_data['company_name'])
        cleaned_data['slug'] = slug

        if slug:
            try:
                if Tenant.objects.filter(slug=slug).exists():
                    self.add_error('slug', f"A tenant with slug '{slug}' already exists.")
            except Exception:
                pass

        return cleaned_data
