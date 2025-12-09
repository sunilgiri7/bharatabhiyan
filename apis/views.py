from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .serializers import (
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    UserSerializer,
    RegistrationPaymentSerializer
)
from accounts.models import RegistrationPayment
import razorpay
import hmac
import hashlib

User = get_user_model()

# Initialize Razorpay Client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


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
def create_razorpay_order(request):
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
    
    if existing_payment and existing_payment.gateway_ref:
        # Return existing order
        return Response({
            'success': True,
            'message': 'Payment order already exists',
            'order_id': existing_payment.gateway_ref,
            'amount': int(existing_payment.amount * 100),  # Convert to paise
            'currency': 'INR',
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'user_name': user.name,
            'user_email': user.email or '',
            'user_phone': user.phone
        }, status=status.HTTP_200_OK)
    
    try:
        # Create Razorpay Order
        razorpay_order = razorpay_client.order.create({
            'amount': 10000,  # ₹100 in paise
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'user_id': str(user_id),
                'payment_type': 'registration'
            }
        })
        
        # Create or update payment record
        if existing_payment:
            existing_payment.gateway_ref = razorpay_order['id']
            existing_payment.save()
            payment = existing_payment
        else:
            payment = RegistrationPayment.objects.create(
                user=user,
                amount=100.00,
                status='PENDING',
                gateway_ref=razorpay_order['id']
            )
        
        return Response({
            'success': True,
            'message': 'Order created successfully',
            'order_id': razorpay_order['id'],
            'amount': razorpay_order['amount'],
            'currency': razorpay_order['currency'],
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'user_name': user.name,
            'user_email': user.email or '',
            'user_phone': user.phone,
            'callback_url': f"{settings.BASE_URL}/api/payments/registration/callback",
            'payment_id': payment.id
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Payment error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_payment(request):
    razorpay_order_id = request.data.get('razorpay_order_id')
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    razorpay_signature = request.data.get('razorpay_signature')
    user_id = request.data.get('user_id')
    
    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, user_id]):
        return Response({
            'success': False,
            'message': 'Missing required payment details'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Verify signature
        generated_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature != razorpay_signature:
            return Response({
                'success': False,
                'message': 'Invalid payment signature'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user and payment
        user = User.objects.get(id=user_id)
        payment = RegistrationPayment.objects.filter(
            user=user,
            gateway_ref=razorpay_order_id,
            status='PENDING'
        ).first()
        
        if not payment:
            payment = RegistrationPayment.objects.filter(
                user=user,
                status='PENDING'
            ).first()
        
        if payment:
            # Update payment status
            payment.status = 'SUCCESS'
            payment.gateway_order_id = razorpay_payment_id
            payment.save()
        
        # Activate user account
        if not user.is_active:
            user.is_active = True
            user.save()
        
        # Generate tokens
        tokens = get_tokens_for_user(user)
        user_data = UserSerializer(user).data
        
        return Response({
            'success': True,
            'message': 'Payment verified and account activated successfully',
            'user': user_data,
            'tokens': tokens
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Verification error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def payment_callback(request):
    """
    Handle Razorpay payment callback (for hosted checkout method)
    POST /api/payments/registration/callback
    """
    if request.method == 'POST':
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_signature = request.POST.get('razorpay_signature')
        
        try:
            # Verify signature
            generated_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()
            
            if generated_signature == razorpay_signature:
                # Payment successful - find user from order
                payment = RegistrationPayment.objects.filter(
                    gateway_ref=razorpay_order_id,
                    status='PENDING'
                ).first()
                
                if payment:
                    user = payment.user
                    
                    # Update payment
                    payment.status = 'SUCCESS'
                    payment.gateway_order_id = razorpay_payment_id
                    payment.save()
                    
                    # Activate user
                    if not user.is_active:
                        user.is_active = True
                        user.save()
                    
                    # Generate tokens
                    tokens = get_tokens_for_user(user)
                    
                    return render(request, 'payment_success.html', {
                        'user': user,
                        'access_token': tokens['access'],
                        'refresh_token': tokens['refresh'],
                        'frontend_url': settings.FRONTEND_URL
                    })
            
            return render(request, 'payment_error.html', {
                'error_message': 'Payment verification failed'
            })
            
        except Exception as e:
            return render(request, 'payment_error.html', {
                'error_message': f'Error: {str(e)}'
            })
    
    return render(request, 'payment_error.html', {
        'error_message': 'Invalid request method'
    })