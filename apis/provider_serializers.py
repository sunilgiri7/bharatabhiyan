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


class ServiceAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceArea
        fields = ['id', 'name', 'location']

class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'category']


class ServiceProviderCreateSerializer(serializers.ModelSerializer):
    # Use ListField to accept arrays of IDs
    service_categories = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=True
    )
    service_types = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=True
    )
    service_areas = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=True
    )
    
    class Meta:
        model = ServiceProvider
        fields = [
            'whatsapp_number', 'business_name', 'experience', 'business_address',
            'city', 'pincode',
            'service_categories', 'service_types', 'service_description',
            'service_areas', 'aadhaar_front', 'aadhaar_back',
            'address_proof_type', 'address_proof', 'profile_photo',
            'skill_certificate',
        ]

    def create(self, validated_data):
        # 1. Extract M2M data
        categories = validated_data.pop('service_categories', [])
        types = validated_data.pop('service_types', [])
        areas = validated_data.pop('service_areas', [])
        
        user = self.context['request'].user
        
        # 2. Create Provider
        provider = ServiceProvider.objects.create(
            user=user, 
            verification_status='DRAFT', # Default status
            **validated_data
        )
        
        # 3. Set Relationships
        provider.service_categories.set(categories)
        provider.service_types.set(types)
        provider.service_areas.set(areas)
        
        return provider


class ServiceProviderUpdateSerializer(serializers.ModelSerializer):
    # Optional ListFields for updates
    service_categories = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    service_types = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    service_areas = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    
    class Meta:
        model = ServiceProvider
        fields = [
            'whatsapp_number', 'business_name', 'experience', 'business_address',
            'city', 'pincode',
            'service_categories', 'service_types', 'service_description',
            'service_areas', 'aadhaar_front', 'aadhaar_back',
            'address_proof_type', 'address_proof', 'profile_photo',
            'skill_certificate',
        ]
    
    def update(self, instance, validated_data):
        # 1. Extract M2M data
        categories = validated_data.pop('service_categories', None)
        types = validated_data.pop('service_types', None)
        areas = validated_data.pop('service_areas', None)
        
        # 2. Update Basic Fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        # 3. Update Relationships (only if provided)
        if categories is not None:
            instance.service_categories.set(categories)
        if types is not None:
            instance.service_types.set(types)
        if areas is not None:
            instance.service_areas.set(areas)
            
        # 4. CRITICAL: Reset Status to DRAFT on update
        instance.verification_status = 'DRAFT'
        instance.rejection_reason = '' # Clear any previous rejection reason
        instance.verified_by = None
        
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
    
    # Updated to return lists
    categories = serializers.SerializerMethodField()
    service_types_list = serializers.SerializerMethodField()
    
    service_areas_list = ServiceAreaSerializer(source='service_areas', many=True, read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.name', read_only=True)
    verified_by_id = serializers.CharField(source='verified_by.id', read_only=True)

    registration_payment_status = serializers.SerializerMethodField()

    class Meta:
        model = ServiceProvider
        fields = [
            'id', 'application_id', 'user_name', 'user_phone', 'user_email',
            'whatsapp_number', 'business_name', 'experience',
            'business_address', 'city', 'city_name', 'state_name', 'pincode',
            'categories', 'service_types_list', # Renamed fields
            'service_description', 'service_areas_list',
            'registration_payment_status',
            'aadhaar_front', 'aadhaar_back', 'address_proof_type', 'address_proof',
            'profile_photo', 'skill_certificate',
            'verification_status', 'verified_by', 'verified_by_name', 'verified_by_id',
            'verification_date', 'rejection_reason',
            'submitted_at', 'created_at', 'updated_at',
        ]

        read_only_fields = [
            'id', 'application_id', 'verification_status', 'verified_by',
            'verification_date', 'rejection_reason', 'submitted_at',
            'created_at', 'updated_at'
        ]

    def get_categories(self, obj):
        return obj.service_categories.values('id', 'name', 'icon')

    def get_service_types_list(self, obj):
        return obj.service_types.values('id', 'name', 'category__name')

    def get_registration_payment_status(self, obj):
        payment = (
            obj.user.registration_payments
            .order_by('-created_at')
            .first()
        )
        return payment.status if payment else None


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
    """Serializer for listing providers with backward compatibility"""
    
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    whatsapp = serializers.CharField(source='whatsapp_number', read_only=True)
    
    city_name = serializers.CharField(source='city.name', read_only=True)
    state_name = serializers.CharField(source='city.state', read_only=True)
    
    # --- New Fields for Lists (The accurate data) ---
    categories = serializers.SerializerMethodField()
    service_types_list = serializers.SerializerMethodField()
    
    # --- Backward Compatibility Fields (Prevent frontend crash) ---
    # These return the FIRST category/type found, so old code still works
    category_id = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    service_type_id = serializers.SerializerMethodField()
    service_type_name = serializers.SerializerMethodField()
    
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
            
            # Both new and old fields
            'categories', 'service_types_list',
            'category_id', 'category_name',
            'service_type_id', 'service_type_name',
            
            'service_description',
            'service_areas_list',
            'profile_photo_url',
            'verification_status',
            'verification_date',
        ]
    
    # New: Return all categories
    def get_categories(self, obj):
        return obj.service_categories.values('id', 'name')

    # New: Return all types
    def get_service_types_list(self, obj):
        return obj.service_types.values('id', 'name')

    # Old: Return just the first one to satisfy legacy frontend
    def get_category_id(self, obj):
        cat = obj.service_categories.first()
        return cat.id if cat else None

    def get_category_name(self, obj):
        cat = obj.service_categories.first()
        return cat.name if cat else None

    def get_service_type_id(self, obj):
        st = obj.service_types.first()
        return st.id if st else None

    def get_service_type_name(self, obj):
        st = obj.service_types.first()
        return st.name if st else None
    
    def get_profile_photo_url(self, obj):
        if obj.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_photo.url)
            return obj.profile_photo.url
        return None