from django.db import models
from django.conf import settings
from locations.models import Location


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, help_text="Emoji or icon identifier")

    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'service_categories'
        verbose_name_plural = 'Service Categories'

    def __str__(self):
        return self.name


class ServiceType(models.Model):
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='service_types')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'service_types'
    
    def __str__(self):
        return f"{self.category.name} - {self.name}"


class ServiceArea(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='service_areas')
    name = models.CharField(max_length=100, help_text="e.g., Sector 1-10, RIICO Industrial Area")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'service_areas'
    
    def __str__(self):
        return f"{self.location.name} - {self.name}"


class ServiceProvider(models.Model):
    EXPERIENCE_CHOICES = [
        ('LESS_THAN_1', 'Less than 1 year'),
        ('1_TO_3', '1-3 years'),
        ('3_TO_5', '3-5 years'),
        ('5_TO_10', '5-10 years'),
        ('MORE_THAN_10', 'More than 10 years'),
    ]
    
    VERIFICATION_STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_VERIFICATION', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]
    
    ADDRESS_PROOF_TYPE_CHOICES = [
        ('ELECTRICITY_BILL', 'Electricity Bill'),
        ('WATER_BILL', 'Water Bill'),
        ('RENT_AGREEMENT', 'Rent Agreement'),
        ('PROPERTY_TAX', 'Property Tax Receipt'),
        ('BANK_STATEMENT', 'Bank Statement'),
    ]
    
    # User relationship
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='provider_profile')
    
    # Basic Information
    whatsapp_number = models.CharField(max_length=15)
    
    # Business Details
    business_name = models.CharField(max_length=255)
    experience = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES)
    business_address = models.TextField()
    city = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, related_name='providers')
    pincode = models.CharField(max_length=10)
    
    # Service Details (UPDATED to ManyToManyField)
    service_categories = models.ManyToManyField(ServiceCategory, related_name='providers')
    service_types = models.ManyToManyField(ServiceType, related_name='providers')
    service_description = models.TextField()
    service_areas = models.ManyToManyField(ServiceArea, related_name='providers')
    
    # Documents
    aadhaar_front = models.FileField(upload_to='provider_docs/aadhaar/', null=True, blank=True)
    aadhaar_back = models.FileField(upload_to='provider_docs/aadhaar/', null=True, blank=True)
    address_proof_type = models.CharField(max_length=30, choices=ADDRESS_PROOF_TYPE_CHOICES, null=True, blank=True)
    address_proof = models.FileField(upload_to='provider_docs/address/', null=True, blank=True)
    profile_photo = models.ImageField(upload_to='provider_docs/photos/', null=True, blank=True)
    skill_certificate = models.FileField(upload_to='provider_docs/certificates/', null=True, blank=True)
    
    # Verification tracking
    application_id = models.CharField(max_length=50, unique=True, editable=False)
    verification_status = models.CharField(max_length=30, choices=VERIFICATION_STATUS_CHOICES, default='DRAFT')
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='verified_providers',
        limit_choices_to={'is_captain': True}
    )
    verification_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'service_providers'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.business_name} - {self.user.name}"
    
    def save(self, *args, **kwargs):
        if not self.application_id:
            # Generate application ID: BA-PRV-YYYY-XXXXX
            from django.utils import timezone
            year = timezone.now().year
            last_provider = ServiceProvider.objects.filter(
                application_id__startswith=f'BA-PRV-{year}'
            ).order_by('-application_id').first()
            
            if last_provider:
                last_num = int(last_provider.application_id.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.application_id = f'BA-PRV-{year}-{new_num:05d}'
        
        super().save(*args, **kwargs)


class ProviderSubscription(models.Model):
    PLAN_CHOICES = [
        ('MONTHLY', 'Monthly Plan'),
        ('YEARLY', 'Yearly Plan'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE, related_name='subscriptions')
    plan_type = models.CharField(max_length=20, choices=PLAN_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    listing_slots = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Payment details
    gateway_order_id = models.CharField(max_length=255, blank=True)
    gateway_payment_id = models.CharField(max_length=255, blank=True)
    
    # Validity
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'provider_subscriptions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.provider.business_name} - {self.plan_type} - {self.status}"
    
class GovernmentService(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class ServiceQuestion(models.Model):
    service = models.ForeignKey(
        GovernmentService,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    question = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question[:60]