from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, phone=None, email=None, password=None, **extra_fields):
        if not phone and not email:
            raise ValueError('Either phone number or email is required')
        
        user = self.model(phone=phone, email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields['is_staff'] = True
        extra_fields['is_superuser'] = True
        extra_fields['is_active'] = True
        extra_fields['is_admin'] = True

        return self.create_user(
            phone=phone,
            password=password,
            **extra_fields
        )


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    
    # Role flags
    is_admin = models.BooleanField(default=False)
    is_captain = models.BooleanField(default=False)
    is_user = models.BooleanField(default=True)
    
    # Captain specific
    captain_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    admin_verified = models.BooleanField(default=False)  # NEW FIELD
    
    # Status flags
    is_active = models.BooleanField(default=True)  
    is_staff = models.BooleanField(default=False)
    
    date_joined = models.DateTimeField(default=timezone.now)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['name']
    
    def clean(self):
        if not self.phone and not self.email:
            raise ValueError('Either phone number or email is required')
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.name} ({self.phone})"


class CaptainProfile(models.Model):
    VERIFICATION_STATUS_CHOICES = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='captain_profile')
    phone = models.CharField(max_length=15)
    aadhaar_front = models.ImageField(upload_to='captain_docs/aadhaar/')
    aadhaar_back = models.ImageField(upload_to='captain_docs/aadhaar/')
    
    verification_status = models.CharField(
        max_length=20, 
        choices=VERIFICATION_STATUS_CHOICES, 
        default='PENDING'
    )
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_captains',
        limit_choices_to={'is_admin': True}
    )
    verification_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'captain_profiles'
        verbose_name = 'Captain Profile'
        verbose_name_plural = 'Captain Profiles'
    
    def __str__(self):
        return f"{self.user.name} - {self.user.captain_code}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    address = models.TextField(blank=True)
    city = models.ForeignKey('locations.Location', on_delete=models.SET_NULL, null=True, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    kyc_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('VERIFIED', 'Verified'),
            ('REJECTED', 'Rejected')
        ],
        default='PENDING'
    )
    
    class Meta:
        db_table = 'user_profiles'
    
    def __str__(self):
        return f"Profile of {self.user.name}"


class RegistrationPayment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='registration_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    gateway_ref = models.CharField(max_length=255, blank=True)
    gateway_order_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'registration_payments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.id} - {self.user.name} - {self.status}"