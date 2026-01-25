from rest_framework import serializers
from providers.models import (
    ServiceProvider, ServiceCategory, ServiceType, 
    ServiceArea, ProviderSubscription
)
from django.utils import timezone


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ['id', 'name', 'icon', 'description']


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'category']


class ServiceAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceArea
        fields = ['id', 'name', 'location']


class ServiceProviderCreateSerializer(serializers.ModelSerializer):
    service_areas = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=True
    )
    
    class Meta:
        model = ServiceProvider
        fields = [
            # Basic Information (auto-filled from user)
            'whatsapp_number',
            
            # Business Details
            'business_name', 'experience', 'business_address',
            'city', 'pincode',
            
            # Service Details
            'service_category', 'service_type', 'service_description',
            'service_areas',
            
            # Documents
            'aadhaar_front', 'aadhaar_back',
            'address_proof_type', 'address_proof',
            'profile_photo', 'skill_certificate',
        ]
    
    def validate_whatsapp_number(self, value):
        if not value.startswith('+91'):
            if len(value) == 10:
                value = f'+91{value}'
            else:
                raise serializers.ValidationError("Invalid WhatsApp number format")
        return value
    
    def validate_service_description(self, value):
        if len(value) < 50:
            raise serializers.ValidationError("Description must be at least 50 characters")
        return value
    
    def validate_service_areas(self, value):
        if not value:
            raise serializers.ValidationError("At least one service area is required")
        # Verify all service area IDs exist
        valid_areas = ServiceArea.objects.filter(id__in=value, is_active=True)
        if len(valid_areas) != len(value):
            raise serializers.ValidationError("Invalid service area selected")
        return value
    
    def validate(self, data):
        # Check if user already has a provider profile
        user = self.context['request'].user
        if ServiceProvider.objects.filter(user=user).exists():
            raise serializers.ValidationError("You already have a service provider profile")
        
        # Validate service type belongs to selected category
        if data.get('service_type') and data.get('service_category'):
            if data['service_type'].category != data['service_category']:
                raise serializers.ValidationError("Service type doesn't match selected category")
        
        return data
    
    def create(self, validated_data):
        service_areas = validated_data.pop('service_areas')
        user = self.context['request'].user
        
        # Create provider profile
        provider = ServiceProvider.objects.create(
            user=user,
            verification_status='DRAFT',
            **validated_data
        )
        
        # Set service areas
        provider.service_areas.set(service_areas)
        
        return provider


class ServiceProviderUpdateSerializer(serializers.ModelSerializer):
    service_areas = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = ServiceProvider
        fields = [
            'whatsapp_number', 'business_name', 'experience', 
            'business_address', 'city', 'pincode',
            'service_category', 'service_type', 'service_description',
            'service_areas', 'aadhaar_front', 'aadhaar_back',
            'address_proof_type', 'address_proof', 'profile_photo',
            'skill_certificate'
        ]
    
    def validate(self, data):
        # Can only update if status is DRAFT or REJECTED
        if self.instance.verification_status not in ['DRAFT', 'REJECTED']:
            raise serializers.ValidationError(
                "Cannot update application after submission"
            )
        return data
    
    def update(self, instance, validated_data):
        service_areas = validated_data.pop('service_areas', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if service_areas is not None:
            instance.service_areas.set(service_areas)
        
        instance.save()
        return instance


class ServiceProviderSubmitSerializer(serializers.Serializer):
    """Serializer for submitting application for verification"""
    confirm_declaration = serializers.BooleanField(required=True)
    accept_terms = serializers.BooleanField(required=True)
    consent_kyc = serializers.BooleanField(required=True)
    
    def validate(self, data):
        if not all([data['confirm_declaration'], data['accept_terms'], data['consent_kyc']]):
            raise serializers.ValidationError("All declarations must be accepted")
        return data


class ServiceProviderDetailSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    state_name = serializers.CharField(source='city.state', read_only=True)
    category_name = serializers.CharField(source='service_category.name', read_only=True)
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    service_areas_list = ServiceAreaSerializer(source='service_areas', many=True, read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.name', read_only=True)
    verified_by_id = serializers.CharField(source='verified_by.id', read_only=True)
    
    class Meta:
        model = ServiceProvider
        fields = [
            'id', 'application_id', 'user_name', 'user_phone', 'user_email',
            'whatsapp_number', 'business_name', 'experience',
            'business_address', 'city', 'city_name', 'state_name', 'pincode',
            'service_category', 'category_name', 'service_type', 'service_type_name',
            'service_description', 'service_areas_list',
            'aadhaar_front', 'aadhaar_back', 'address_proof_type', 'address_proof',
            'profile_photo', 'skill_certificate',
            'verification_status', 'verified_by', 'verified_by_name', 'verified_by_id',
            'verification_date', 'rejection_reason',
            'submitted_at', 'created_at', 'updated_at',
            'has_active_subscription',
            'active_plan',
            'subscription_end_date',
        ]
        read_only_fields = [
            'id', 'application_id', 'verification_status', 'verified_by',
            'verification_date', 'rejection_reason', 'submitted_at', 
            'created_at', 'updated_at'
        ]

        def get_has_active_subscription(self, obj):
            return obj.subscriptions.filter(
            status='ACTIVE',
            end_date__gte=timezone.now()
            ).exists()


        def get_active_plan(self, obj):
            sub = obj.subscriptions.filter(
            status='ACTIVE',
            end_date__gte=timezone.now()
            ).first()
            return sub.plan_type if sub else None


        def get_subscription_end_date(self, obj):
            sub = obj.subscriptions.filter(
            status='ACTIVE',
            end_date__gte=timezone.now()
            ).first()
            return sub.end_date if sub else None


class ProviderSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ProviderSubscription
        fields = [
            'id', 'plan_type', 'plan_name', 'amount', 'listing_slots',
            'status', 'start_date', 'end_date', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'start_date', 'end_date', 'created_at']
    
    def get_plan_name(self, obj):
        return dict(ProviderSubscription.PLAN_CHOICES).get(obj.plan_type, '')


class ProviderSubscriptionCreateSerializer(serializers.Serializer):
    plan_type = serializers.ChoiceField(choices=['MONTHLY', 'YEARLY'])
    
    def validate(self, data):
        user = self.context['request'].user
        
        # Check if provider profile exists and is verified
        try:
            provider = user.provider_profile
            if provider.verification_status != 'VERIFIED':
                raise serializers.ValidationError(
                    "Your provider profile must be verified before subscribing"
                )
        except ServiceProvider.DoesNotExist:
            raise serializers.ValidationError("Provider profile not found")
        
        # Check for existing pending subscription
        pending_sub = ProviderSubscription.objects.filter(
            provider=provider,
            status='PENDING'
        ).first()
        
        if pending_sub:
            raise serializers.ValidationError({
                'message': 'Pending subscription already exists',
                'subscription_id': pending_sub.id
            })
        
        return data

class ServiceProviderListSerializer(serializers.ModelSerializer):
    """Serializer for listing providers with essential details"""
    
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    whatsapp = serializers.CharField(source='whatsapp_number', read_only=True)
    
    city_name = serializers.CharField(source='city.name', read_only=True)
    state_name = serializers.CharField(source='city.state', read_only=True)
    
    category_id = serializers.IntegerField(source='service_category.id', read_only=True)
    category_name = serializers.CharField(source='service_category.name', read_only=True)
    
    service_type_id = serializers.IntegerField(source='service_type.id', read_only=True)
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    
    service_areas_list = ServiceAreaSerializer(source='service_areas', many=True, read_only=True)
    
    profile_photo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceProvider
        fields = [
            'id',
            'application_id',
            'user_name',
            'user_phone',
            'whatsapp',
            'business_name',
            'experience',
            'business_address',
            'city_name',
            'state_name',
            'pincode',
            'category_id',
            'category_name',
            'service_type_id',
            'service_type_name',
            'service_description',
            'service_areas_list',
            'profile_photo_url',
            'verification_status',
            'verification_date',
        ]
    
    def get_profile_photo_url(self, obj):
        if obj.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_photo.url)
            return obj.profile_photo.url
        return None