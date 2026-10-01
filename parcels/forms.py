from django import forms
from django.contrib.auth.models import User
from .models import (
    Parcel, Branch, ShippingRate, TransitManifest,
    PickupRequest, CustomerInquiry, UserProfile
)


class UserLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none',
            'placeholder': 'Enter your username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none',
            'placeholder': '••••••••'
        })
    )


class CustomerRegisterForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'}))
    phone = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'}))
    city = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'}),
        }


class ParcelBookingForm(forms.ModelForm):
    class Meta:
        model = Parcel
        fields = [
            'sender_name', 'sender_phone', 'sender_email', 'sender_address', 'sender_city',
            'receiver_name', 'receiver_phone', 'receiver_email', 'receiver_address', 'receiver_city',
            'origin_branch', 'destination_branch', 'delivery_type', 'service_type', 'category',
            'item_description', 'weight_kg', 'length_cm', 'width_cm', 'height_cm',
            'is_fragile', 'declared_value', 'payment_method', 'payment_status'
        ]
        widgets = {
            'sender_name': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Full Name'}),
            'sender_phone': forms.TextInput(attrs={'class': 'input-control', 'placeholder': '+1 (555) 000-0000'}),
            'sender_email': forms.EmailInput(attrs={'class': 'input-control', 'placeholder': 'sender@example.com'}),
            'sender_address': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Street Address / Apt'}),
            'sender_city': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'City'}),

            'receiver_name': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Recipient Name'}),
            'receiver_phone': forms.TextInput(attrs={'class': 'input-control', 'placeholder': '+1 (555) 000-0000'}),
            'receiver_email': forms.EmailInput(attrs={'class': 'input-control', 'placeholder': 'receiver@example.com'}),
            'receiver_address': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Destination Address or Branch Hold'}),
            'receiver_city': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'City'}),

            'origin_branch': forms.Select(attrs={'class': 'select-control'}),
            'destination_branch': forms.Select(attrs={'class': 'select-control'}),
            'delivery_type': forms.Select(attrs={'class': 'select-control'}),
            'service_type': forms.Select(attrs={'class': 'select-control', 'id': 'id_service_type'}),
            'category': forms.Select(attrs={'class': 'select-control'}),
            
            'item_description': forms.Textarea(attrs={'class': 'input-control', 'rows': 2, 'placeholder': 'Brief description of contents (e.g., Electronics, Documents)'}),
            'weight_kg': forms.NumberInput(attrs={'class': 'input-control', 'step': '0.1', 'min': '0.1', 'id': 'id_weight_kg'}),
            'length_cm': forms.NumberInput(attrs={'class': 'input-control', 'step': '1', 'min': '1', 'id': 'id_length_cm'}),
            'width_cm': forms.NumberInput(attrs={'class': 'input-control', 'step': '1', 'min': '1', 'id': 'id_width_cm'}),
            'height_cm': forms.NumberInput(attrs={'class': 'input-control', 'step': '1', 'min': '1', 'id': 'id_height_cm'}),
            
            'is_fragile': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-blue-600 rounded border-gray-300 focus:ring-blue-500', 'id': 'id_is_fragile'}),
            'declared_value': forms.NumberInput(attrs={'class': 'input-control', 'step': '0.01', 'min': '0.00', 'id': 'id_declared_value'}),
            'payment_method': forms.Select(attrs={'class': 'select-control'}),
            'payment_status': forms.Select(attrs={'class': 'select-control'}),
        }


class ParcelStatusUpdateForm(forms.Form):
    status = forms.ChoiceField(
        choices=Parcel.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'select-control'})
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'select-control'})
    )
    location_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'e.g. NYC Central Hub - Bay 2'})
    )
    activity = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'e.g. Package arrived and sorted for delivery route'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'input-control', 'rows': 2, 'placeholder': 'Optional internal operational note'})
    )


class CourierAssignmentForm(forms.Form):
    courier = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__role='COURIER'),
        required=True,
        widget=forms.Select(attrs={'class': 'select-control'})
    )
    delivery_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'input-control', 'rows': 2, 'placeholder': 'Special delivery route notes for courier'})
    )


class CourierDeliveryActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=[
            ('DELIVER', 'Mark as Delivered'),
            ('FAILED', 'Mark Delivery Attempt Failed'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'mr-2'})
    )
    receiver_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Name of person receiving the package'})
    )
    security_otp = forms.CharField(
        max_length=6,
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-control', 'placeholder': '6-digit OTP provided by recipient'})
    )
    delivery_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'input-control', 'rows': 2, 'placeholder': 'Proof note, gate code remarks, or reason for failure'})
    )


class TransitManifestForm(forms.ModelForm):
    class Meta:
        model = TransitManifest
        fields = ['origin_branch', 'destination_branch', 'driver_name', 'driver_phone', 'vehicle_plate', 'notes']
        widgets = {
            'origin_branch': forms.Select(attrs={'class': 'select-control'}),
            'destination_branch': forms.Select(attrs={'class': 'select-control'}),
            'driver_name': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Driver Full Name'}),
            'driver_phone': forms.TextInput(attrs={'class': 'input-control', 'placeholder': '+1 (555) 000-0000'}),
            'vehicle_plate': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'e.g. TRK-4921'}),
            'notes': forms.Textarea(attrs={'class': 'input-control', 'rows': 2, 'placeholder': 'Trip instructions or route notes'}),
        }


class PickupRequestForm(forms.ModelForm):
    class Meta:
        model = PickupRequest
        fields = [
            'customer_name', 'customer_phone', 'customer_email',
            'pickup_address', 'pickup_city', 'preferred_date',
            'preferred_time_slot', 'estimated_weight_kg', 'package_description', 'notes'
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Your Full Name'}),
            'customer_phone': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Contact Phone Number'}),
            'customer_email': forms.EmailInput(attrs={'class': 'input-control', 'placeholder': 'Email Address'}),
            'pickup_address': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Complete Street Address / Apt / Floor'}),
            'pickup_city': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'City'}),
            'preferred_date': forms.DateInput(attrs={'class': 'input-control', 'type': 'date'}),
            'preferred_time_slot': forms.Select(attrs={'class': 'select-control'}),
            'estimated_weight_kg': forms.NumberInput(attrs={'class': 'input-control', 'step': '0.5', 'min': '0.5'}),
            'package_description': forms.Textarea(attrs={'class': 'input-control', 'rows': 2, 'placeholder': 'Describe items and approximate count'}),
            'notes': forms.Textarea(attrs={'class': 'input-control', 'rows': 2, 'placeholder': 'Gate code, parking instructions, etc.'}),
        }


class CustomerInquiryForm(forms.ModelForm):
    class Meta:
        model = CustomerInquiry
        fields = ['name', 'email', 'phone', 'tracking_number', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Your Name'}),
            'email': forms.EmailInput(attrs={'class': 'input-control', 'placeholder': 'Your Email'}),
            'phone': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Your Phone (optional)'}),
            'tracking_number': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Tracking Number (if applicable)'}),
            'subject': forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'Subject of inquiry'}),
            'message': forms.Textarea(attrs={'class': 'input-control', 'rows': 4, 'placeholder': 'Please provide details of your question or issue...'}),
        }


class InquiryReplyForm(forms.Form):
    status = forms.ChoiceField(
        choices=CustomerInquiry.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'select-control'})
    )
    staff_reply = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'input-control', 'rows': 4, 'placeholder': 'Type official response to customer...'})
    )
