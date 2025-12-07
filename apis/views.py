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
import stripe

User = get_user_model()

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


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
    user = request.user
    serializer = UserSerializer(user)
    
    return Response({
        'success': True,
        'user': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_registration_payment_checkout(request):
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
    
    if existing_payment and existing_payment.gateway_order_id:
        # Return existing checkout URL if still valid
        return Response({
            'success': True,
            'message': 'Payment session already exists',
            'checkout_url': existing_payment.gateway_order_id,
            'payment_id': existing_payment.id
        }, status=status.HTTP_200_OK)
    
    try:
        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'unit_amount': 10000,  # ₹100 in paise
                    'product_data': {
                        'name': 'BharatAbhiyan Registration Fee',
                        'description': 'One-time registration fee to activate your account',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{settings.PAYMENT_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{settings.PAYMENT_FAILURE_URL}?user_id={user_id}',
            client_reference_id=str(user_id),
            metadata={
                'user_id': user_id,
                'payment_type': 'registration'
            }
        )
        
        # Create or update payment record
        if existing_payment:
            existing_payment.gateway_order_id = checkout_session.url
            existing_payment.gateway_ref = checkout_session.id
            existing_payment.save()
            payment = existing_payment
        else:
            payment = RegistrationPayment.objects.create(
                user=user,
                amount=100.00,
                status='PENDING',
                gateway_order_id=checkout_session.url,
                gateway_ref=checkout_session.id
            )
        
        return Response({
            'success': True,
            'message': 'Checkout session created',
            'checkout_url': checkout_session.url,
            'payment_id': payment.id
        }, status=status.HTTP_201_CREATED)
        
    except stripe.error.StripeError as e:
        return Response({
            'success': False,
            'message': f'Payment error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def payment_success(request):
    """
    Handle successful payment redirect from Stripe
    GET /payment/success?session_id=xxx
    """
    session_id = request.GET.get('session_id')
    
    if not session_id:
        return render(request, 'payment_error.html', {
            'error_message': 'Invalid payment session'
        })
    
    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            user_id = session.client_reference_id or session.metadata.get('user_id')
            
            # Find user and payment record
            user = User.objects.get(id=user_id)
            payment = RegistrationPayment.objects.filter(
                user=user,
                gateway_ref=session_id
            ).first()
            
            if not payment:
                # Try to find by session id in gateway_ref
                payment = RegistrationPayment.objects.filter(
                    user=user,
                    status='PENDING'
                ).first()
            
            if payment:
                # Update payment status
                payment.status = 'SUCCESS'
                payment.gateway_ref = session_id
                payment.save()
            
            # Activate user account
            if not user.is_active:
                user.is_active = True
                user.save()
            
            # Generate tokens for the user
            tokens = get_tokens_for_user(user)
            
            return render(request, 'payment_success.html', {
                'user': user,
                'access_token': tokens['access'],
                'refresh_token': tokens['refresh'],
                'frontend_url': settings.FRONTEND_URL
            })
        else:
            return render(request, 'payment_error.html', {
                'error_message': 'Payment not completed'
            })
            
    except stripe.error.StripeError as e:
        return render(request, 'payment_error.html', {
            'error_message': f'Payment verification failed: {str(e)}'
        })
    except User.DoesNotExist:
        return render(request, 'payment_error.html', {
            'error_message': 'User not found'
        })
    except Exception as e:
        return render(request, 'payment_error.html', {
            'error_message': f'An error occurred: {str(e)}'
        })


@csrf_exempt
def payment_failure(request):
    """
    Handle failed/cancelled payment redirect from Stripe
    GET /payment/failure?user_id=xxx
    """
    user_id = request.GET.get('user_id')
    
    context = {
        'frontend_url': settings.FRONTEND_URL,
        'user_id': user_id
    }
    
    return render(request, 'payment_failure.html', context)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """
    Handle Stripe webhook events (optional but recommended)
    POST /api/payments/webhook
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return Response({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return Response({'error': 'Invalid signature'}, status=400)
    
    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        if session.payment_status == 'paid':
            user_id = session.client_reference_id or session.metadata.get('user_id')
            
            try:
                user = User.objects.get(id=user_id)
                
                # Update payment
                payment = RegistrationPayment.objects.filter(
                    user=user,
                    status='PENDING'
                ).first()
                
                if payment:
                    payment.status = 'SUCCESS'
                    payment.gateway_ref = session.id
                    payment.save()
                
                # Activate user
                if not user.is_active:
                    user.is_active = True
                    user.save()
                    
            except User.DoesNotExist:
                pass
    
    return Response({'status': 'success'}, status=200)