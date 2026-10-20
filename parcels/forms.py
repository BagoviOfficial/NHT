from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from decimal import Decimal
from routes.models import Route
from core.services import apply_dynamic_field_configs, get_active_choices
from .models import Parcel, ShipmentItem, PaymentStatus, PaymentMethod


class ParcelForm(forms.ModelForm):
    route = forms.ModelChoiceField(
        queryset=Route.objects.filter(is_active=True),
        empty_label="-- Select Destination Route --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Parcel
        fields = [
            'route',
            'sender_name', 'sender_phone',
            'receiver_name', 'receiver_phone', 'receiver_id_number',
            'payment_status', 'payment_method'
        ]
        widgets = {
            'sender_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'sender_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254 7...'}),
            'receiver_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'receiver_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254 7...'}),
            'receiver_id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID / Passport Number'}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['route'].queryset = Route.objects.filter(tenant=tenant, is_active=True)
        apply_dynamic_field_configs(self, tenant=tenant)
        
        # Override choices if ChoiceConfig exists
        dynamic_pay_statuses = get_active_choices('payment_status', tenant=tenant)
        if dynamic_pay_statuses:
            self.fields['payment_status'].choices = dynamic_pay_statuses

        dynamic_pay_methods = get_active_choices('payment_method', tenant=tenant)
        if dynamic_pay_methods:
            self.fields['payment_method'].choices = dynamic_pay_methods


class ShipmentItemForm(forms.ModelForm):
    class Meta:
        model = ShipmentItem
        fields = ['description', 'wrap_type', 'quantity', 'unit_price']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control item-desc', 'placeholder': 'Item description'}),
            'wrap_type': forms.TextInput(attrs={'class': 'form-control item-wrap', 'placeholder': 'e.g. Box, Sack, Carton'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control item-qty', 'min': 1, 'value': 1}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control item-price', 'min': 0, 'step': '0.01', 'value': '0.00'}),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if not qty or qty < 1:
            raise ValidationError("Quantity must be at least 1.")
        if qty > 10000:
            raise ValidationError("Quantity cannot exceed 10,000 units.")
        return qty

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price')
        if price is None or price < Decimal('0.00'):
            raise ValidationError("Unit price cannot be negative.")
        if price > Decimal('10000000.00'):
            raise ValidationError("Unit price exceeds maximum allowable limit (10,000,000.00).")
        return price


class BaseShipmentItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        valid_items_count = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                valid_items_count += 1

        if valid_items_count < 1:
            raise ValidationError("A shipment must contain at least one valid item.")


ShipmentItemFormSet = inlineformset_factory(
    Parcel,
    ShipmentItem,
    form=ShipmentItemForm,
    formset=BaseShipmentItemFormSet,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class DispatchForm(forms.Form):
    truck_plate_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. KAA 123A'}),
        help_text="Registration plate of the dispatched bus/truck."
    )
    driver_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name of Driver'}),
        help_text="Name of the driver in charge of the vehicle."
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional dispatch notes'}),
        help_text="Additional operational remarks."
    )


class ArrivalForm(forms.Form):
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'e.g. Arrived safely, luggage inspected'}),
        help_text="Optional arrival notes."
    )


class CollectionForm(forms.Form):
    collected_by_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name of Collector'}),
        help_text="Name of individual claiming parcel (must match ID verification)."
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional collection notes / ID check'}),
        help_text="Collector notes."
    )


class CancelForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for cancellation'}),
        help_text="Mandatory audit explanation for cancelling this parcel."
    )


class AdminOverrideForm(forms.ModelForm):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mandatory administrative justification'}),
        help_text="State why this shipment data is being altered post-dispatch."
    )

    class Meta:
        model = Parcel
        fields = [
            'route', 'truck_plate_number', 'driver_name',
            'sender_name', 'sender_phone',
            'receiver_name', 'receiver_phone', 'receiver_id_number',
            'payment_status', 'payment_method', 'price'
        ]
        widgets = {
            'route': forms.Select(attrs={'class': 'form-select'}),
            'truck_plate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'driver_name': forms.TextInput(attrs={'class': 'form-control'}),
            'sender_name': forms.TextInput(attrs={'class': 'form-control'}),
            'sender_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'receiver_name': forms.TextInput(attrs={'class': 'form-control'}),
            'receiver_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'receiver_id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = None
        if self.instance and getattr(self.instance, 'tenant_id', None):
            tenant = self.instance.tenant
        if tenant:
            self.fields['route'].queryset = Route.objects.filter(tenant=tenant)
