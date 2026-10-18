from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from routes.models import Route
from .models import User, Role


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username or Staff ID', 'autofocus': True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Temporary Password'}),
        min_length=8,
        help_text="Minimum 8 characters."
    )
    assigned_route = forms.ModelChoiceField(
        queryset=Route.objects.filter(is_active=True),
        required=False,
        empty_label="-- Select Branch/Route (For Destination Staff) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'phone', 'email', 'role', 'assigned_route', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254 7...'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['assigned_route'].queryset = Route.objects.filter(tenant=tenant, is_active=True)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError("Staff phone number is required.")
        if User.objects.filter(phone=phone).exists():
            raise ValidationError("A staff user with this phone number already exists.")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        route = cleaned_data.get('assigned_route')

        if role == Role.DESTINATION_STAFF and not route:
            self.add_error('assigned_route', "Destination Collection Staff must be assigned to a specific branch route.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    assigned_route = forms.ModelChoiceField(
        queryset=Route.objects.filter(is_active=True),
        required=False,
        empty_label="-- Select Branch/Route (For Destination Staff) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'email', 'role', 'assigned_route', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        t = tenant or (self.instance.tenant if self.instance and self.instance.tenant_id else None)
        if t:
            self.fields['assigned_route'].queryset = Route.objects.filter(tenant=t, is_active=True)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError("Staff phone number is required.")
        if User.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Another staff user already has this phone number.")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        route = cleaned_data.get('assigned_route')

        if role == Role.DESTINATION_STAFF and not route:
            self.add_error('assigned_route', "Destination Collection Staff must be assigned to a specific branch route.")
        return cleaned_data


class AdminPasswordResetForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'}),
        min_length=8
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm New Password'}),
        min_length=8
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return cleaned_data
