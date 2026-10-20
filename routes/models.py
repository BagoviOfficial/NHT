from django.db import models
from django.utils.text import slugify


class Route(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='routes',
        help_text="Client organization this route belongs to."
    )
    name = models.CharField(max_length=100, db_index=True, help_text="Destination town or stop (e.g. Mandera, Garissa)")
    slug = models.SlugField(max_length=120, db_index=True)
    origin = models.CharField(max_length=100, default='Nairobi', help_text="Origin terminal (defaults to Nairobi HQ)")
    description = models.TextField(blank=True, help_text="Transit notes or stopover details")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Inactive routes cannot be selected for new parcels")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Route'
        verbose_name_plural = 'Routes'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='unique_tenant_route_name'),
            models.UniqueConstraint(fields=['tenant', 'slug'], name='unique_tenant_route_slug'),
        ]

    def __str__(self):
        return f"{self.origin} -> {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            qs = Route.objects.filter(tenant=self.tenant, slug=slug).exclude(pk=self.pk)
            while qs.exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                qs = Route.objects.filter(tenant=self.tenant, slug=slug).exclude(pk=self.pk)
            self.slug = slug
        super().save(*args, **kwargs)

    def can_be_deleted(self):
        """Check if any parcels or destination staff members reference this route to prevent dangling assignments."""
        return not self.parcels.exists() and not self.assigned_staff.exists()
