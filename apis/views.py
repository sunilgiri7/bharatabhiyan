from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from .serializers import (
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    UserSerializer,
    RegistrationPaymentSerializer
)
from accounts.models import RegistrationPayment
import uuid

User = get_user_model()


def get_tokens_for_user(user):
    """Generate JWT tokens for user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register new user
    POST /api/auth/register
    Body: {phone, email, name, password}
    Returns: user data with is_active=False (needs payment)
    """
    serializer = UserRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        user_data = UserSerializer(user).data
        
        return Response({
            'success': True,
            'message': 'Registration successful. Please complete payment to activate account.',
            'user': user_data,
            'user_id': user.id
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Login user
    POST /api/auth/login
    Body: {phone, password}
    Returns: JWT tokens + user data
    """
    serializer = UserLoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    phone = serializer.validated_data['phone']
    password = serializer.validated_data['password']
    
    # Authenticate user
    user = authenticate(request, phone=phone, password=password)
    
    if user is None:
        return Response({
            'success': False,
            'message': 'Invalid phone number or password'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Check if account is active (paid)
    if not user.is_active:
        return Response({
            'success': False,
            'message': 'Account not activated. Please complete payment.',
            'user_id': user.id,
            'requires_payment': True
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Generate tokens
    tokens = get_tokens_for_user(user)
    user_data = UserSerializer(user).data
    
    return Response({
        'success': True,
        'message': 'Login successful',
        'user': user_data,
        'tokens': tokens
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    Get current user details
    GET /api/auth/me
    Headers: Authorization: Bearer <access_token>
    """
    user = request.user
    serializer = UserSerializer(user)
    
    return Response({
        'success': True,
        'user': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_registration_payment_order(request):
    """
    Create payment order for registration (₹100)
    POST /api/payments/registration/create-order
    Body: {user_id}
    Returns: payment order details
    """
    user_id = request.data.get('user_id')
    
    if not user_id:
        return Response({
            'success': False,
            'message': 'user_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if user.is_active:
        return Response({
            'success': False,
            'message': 'User account already activated'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if pending payment exists
    existing_payment = RegistrationPayment.objects.filter(
        user=user, 
        status='PENDING'
    ).first()
    
    if existing_payment:
        serializer = RegistrationPaymentSerializer(existing_payment)
        return Response({
            'success': True,
            'message': 'Payment order already exists',
            'payment': serializer.data,
            'gateway_order_id': existing_payment.gateway_order_id
        }, status=status.HTTP_200_OK)
    
    # Create new payment record
    gateway_order_id = f"order_{uuid.uuid4().hex[:12]}"  # Mock order ID
    
    payment = RegistrationPayment.objects.create(
        user=user,
        amount=100.00,
        status='PENDING',
        gateway_order_id=gateway_order_id
    )
    
    serializer = RegistrationPaymentSerializer(payment)
    
    return Response({
        'success': True,
        'message': 'Payment order created',
        'payment': serializer.data,
        'gateway_order_id': gateway_order_id,
        'amount': 100.00
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_registration_payment(request):
    """
    Verify payment and activate user account
    POST /api/payments/registration/verify
    Body: {user_id, gateway_order_id, gateway_ref}
    """
    user_id = request.data.get('user_id')
    gateway_order_id = request.data.get('gateway_order_id')
    gateway_ref = request.data.get('gateway_ref')
    
    if not all([user_id, gateway_order_id]):
        return Response({
            'success': False,
            'message': 'user_id and gateway_order_id are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(id=user_id)
        payment = RegistrationPayment.objects.get(
            user=user,
            gateway_order_id=gateway_order_id,
            status='PENDING'
        )
    except (User.DoesNotExist, RegistrationPayment.DoesNotExist):
        return Response({
            'success': False,
            'message': 'Invalid payment details'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Update payment status
    payment.status = 'SUCCESS'
    payment.gateway_ref = gateway_ref or ''
    payment.save()
    
    # Activate user account
    user.is_active = True
    user.save()
    
    # Generate tokens for automatic login
    tokens = get_tokens_for_user(user)
    user_data = UserSerializer(user).data
    
    return Response({
        'success': True,
        'message': 'Payment verified and account activated successfully',
        'user': user_data,
        'tokens': tokens
    }, status=status.HTTP_200_OK)