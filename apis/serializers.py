from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.models import UserProfile, RegistrationPayment

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = ['phone', 'email', 'name', 'password']
    
    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone number already registered")
        return value
    
    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        
        if password:
            user.set_password(password)
            user.save()
        
        # Create profile automatically
        UserProfile.objects.create(user=user)
        
        return user


class UserLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone', 'email', 'name', 'is_active', 'is_admin', 'is_captain', 'date_joined']
        read_only_fields = ['id', 'is_active', 'is_admin', 'is_captain', 'date_joined']


class RegistrationPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationPayment
        fields = ['id', 'amount', 'status', 'gateway_order_id', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']