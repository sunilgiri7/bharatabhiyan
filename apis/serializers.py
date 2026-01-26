from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.models import UserProfile, RegistrationPayment
from django.utils import timezone
User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['phone', 'email', 'name', 'password']
    
    def validate(self, data):
        phone = data.get('phone', '').strip() if data.get('phone') else ''
        email = data.get('email', '').strip() if data.get('email') else ''
        
        if not phone and not email:
            raise serializers.ValidationError("Either phone number or email is required")
        
        return data
    
    def validate_phone(self, value):
        if value:
            value = value.strip()
            if User.objects.filter(phone=value).exists():
                raise serializers.ValidationError("Phone number already registered")
        return value
    
    def validate_email(self, value):
        if value:
            value = value.strip()
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("Email already registered")
        return value
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        # Clean up empty strings to None
        phone = validated_data.get('phone')
        email = validated_data.get('email')
        
        validated_data['phone'] = phone.strip() if phone else None
        validated_data['email'] = email.strip() if email else None
        
        user = User.objects.create(**validated_data)
        
        if password:
            user.set_password(password)
            user.save()
        
        # Create profile automatically
        UserProfile.objects.create(user=user)
        
        return user


class UserLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        phone = data.get('phone', '').strip() if data.get('phone') else ''
        email = data.get('email', '').strip() if data.get('email') else ''
        
        if not phone and not email:
            raise serializers.ValidationError("Either phone number or email is required")
        
        return data

class UserSerializer(serializers.ModelSerializer):
    is_provider = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'phone', 'email', 'name',
            'is_active', 'is_admin', 'is_captain', 'date_joined',
            'is_provider',
            'subscription_status',
        ]

        read_only_fields = [
            'id', 'is_active', 'is_admin', 'is_captain', 'date_joined'
        ]

    def get_is_provider(self, obj):
        return hasattr(obj, 'provider_profile')

    def get_subscription_status(self, obj):
        if not hasattr(obj, 'provider_profile'):
            return None

        sub = (
            obj.provider_profile.subscriptions
            .order_by('-created_at')
            .first()
        )

        return sub.status if sub else None


class RegistrationPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationPayment
        fields = ['id', 'amount', 'status', 'gateway_order_id', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']