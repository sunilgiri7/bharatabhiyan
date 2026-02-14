from providers.models import GovernmentService, ServiceQuestion, ServiceQuestionAnswer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.models import UserProfile, RegistrationPayment
from django.utils import timezone
User = get_user_model()
import random
import string

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    is_captain = serializers.BooleanField(required=False, default=False)
    is_provider = serializers.BooleanField(required=False, default=False)
    
    class Meta:
        model = User
        fields = ['phone', 'email', 'name', 'password', 'is_captain', 'is_provider']
    
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
    
    def generate_unique_captain_code(self):
        """Generate a unique captain code"""
        while True:
            code = 'CAP' + ''.join(random.choices(string.digits, k=8))
            if not User.objects.filter(captain_code=code).exists():
                return code
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        is_captain = validated_data.pop('is_captain', False)
        is_provider = validated_data.pop('is_provider', False)
        
        # Clean up empty strings to None
        phone = validated_data.get('phone')
        email = validated_data.get('email')
        
        validated_data['phone'] = phone.strip() if phone else None
        validated_data['email'] = email.strip() if email else None
        
        # Set role flags based on logic
        validated_data['is_captain'] = is_captain
        validated_data['is_user'] = not (is_captain or is_provider)
        
        # Generate captain code if is_captain is True
        if is_captain:
            validated_data['captain_code'] = self.generate_unique_captain_code()
            validated_data['admin_verified'] = False  # Captain needs admin verification
        else:
            validated_data['admin_verified'] = True  # Regular users don't need admin verification
        
        user = User.objects.create(**validated_data)
        
        if password:
            user.set_password(password)
            user.save()
        
        # Create profile automatically
        UserProfile.objects.create(user=user)
        
        # Create provider profile if is_provider is True
        if is_provider:
            from providers.models import ProviderProfile
            ProviderProfile.objects.create(user=user)
        
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
    registration_payment_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'phone', 'email', 'name',
            'is_active', 'is_admin', 'is_captain', 'is_user',
            'captain_code', 'admin_verified',  # Added admin_verified
            'date_joined',
            'is_provider',
            'registration_payment_status',
        ]

        read_only_fields = [
            'id', 'is_active', 'is_admin', 'is_captain', 'is_user', 
            'captain_code', 'admin_verified', 'date_joined'
        ]

    def get_is_provider(self, obj):
        return hasattr(obj, 'provider_profile')

    def get_registration_payment_status(self, obj):
        payment = (
            obj.registration_payments
            .order_by('-created_at')
            .first()
        )
        return payment.status if payment else None


class RegistrationPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationPayment
        fields = ['id', 'amount', 'status', 'gateway_order_id', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

class ServiceQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceQuestion
        fields = ["id", "question"]


class GovernmentServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GovernmentService
        fields = ["id", "name", "description"]


class GovernmentServiceWithQuestionsSerializer(serializers.ModelSerializer):
    questions = ServiceQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = GovernmentService
        fields = ["id", "name", "description", "questions"]

class ServiceQuestionAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.question', read_only=True)
    service_name = serializers.CharField(source='question.service.name', read_only=True)
    
    class Meta:
        model = ServiceQuestionAnswer
        fields = ["id", "question", "question_text", "service_name", 
                  "answer_english", "answer_hindi", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]