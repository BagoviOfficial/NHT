from django.test import TestCase
from django.core.cache import cache
from django.core.exceptions import ValidationError
from .models import SiteSettings, FieldConfig, ChoiceConfig
from .services import get_site_settings, get_field_configs, get_active_choices, apply_dynamic_field_configs
from parcels.forms import ParcelForm
from routes.models import Route


class DynamicConfigurationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.route = Route.objects.create(name="Garissa")

    def test_site_settings_singleton_and_cache(self):
        s1 = SiteSettings.load()
        self.assertEqual(s1.company_name, "Northern Highways Transporters")

        s1.company_name = "NHT Express Logistics"
        s1.save()

        s2 = get_site_settings()
        self.assertEqual(s2.company_name, "NHT Express Logistics")

    def test_invalid_field_key_rejected(self):
        cfg = FieldConfig(
            field_key="arbitrary_unsafe_key",
            label="Malicious Field"
        )
        with self.assertRaises(ValidationError):
            cfg.clean()

    def test_valid_field_config_updates_form(self):
        FieldConfig.objects.create(
            field_key='sender_name',
            label='Full Legal Sender Name',
            placeholder='e.g. John Doe',
            is_required=True
        )
        cache.clear()

        form = ParcelForm()
        apply_dynamic_field_configs(form)
        self.assertEqual(form.fields['sender_name'].label, 'Full Legal Sender Name')
        self.assertEqual(form.fields['sender_name'].widget.attrs.get('placeholder'), 'e.g. John Doe')

    def test_choice_config_category_validation(self):
        c = ChoiceConfig(category="unsafe_category", key="k", label="l")
        with self.assertRaises(ValidationError):
            c.clean()

    def test_active_choices_retrieval(self):
        ChoiceConfig.objects.create(category='wrap_type', key='Drum', label='Metal Drum', is_active=True)
        ChoiceConfig.objects.create(category='wrap_type', key='Hidden', label='Hidden Wrap', is_active=False)
        cache.clear()

        choices = get_active_choices('wrap_type')
        keys = [k for k, _ in choices]
        self.assertIn('Drum', keys)
        self.assertNotIn('Hidden', keys)

    def test_field_config_hidden_and_optional_and_cache_invalidation(self):
        cfg = FieldConfig.objects.create(
            field_key='receiver_id_number',
            label='National ID',
            is_required=False,
            is_visible=False
        )
        form = ParcelForm()
        apply_dynamic_field_configs(form)
        self.assertFalse(form.fields['receiver_id_number'].required)
        self.assertIn('display:none;', form.fields['receiver_id_number'].widget.attrs.get('style', ''))

        # Update and verify cache invalidation
        cfg.is_visible = True
        cfg.is_required = True
        cfg.save()

        form2 = ParcelForm()
        apply_dynamic_field_configs(form2)
        self.assertTrue(form2.fields['receiver_id_number'].required)
        self.assertNotIn('display:none;', form2.fields['receiver_id_number'].widget.attrs.get('style', ''))

    def test_choice_config_cache_invalidation_and_form_override(self):
        c = ChoiceConfig.objects.create(category='payment_method', key='CRYPTO', label='Crypto Token', is_active=True)
        form = ParcelForm()
        method_keys = [k for k, _ in form.fields['payment_method'].choices]
        self.assertIn('CRYPTO', method_keys)

        # Deactivate and check cache is invalidated
        c.is_active = False
        c.save()
        form2 = ParcelForm()
        method_keys2 = [k for k, _ in form2.fields['payment_method'].choices]
        self.assertNotIn('CRYPTO', method_keys2)

