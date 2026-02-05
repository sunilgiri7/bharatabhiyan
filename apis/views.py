from providers.models import GovernmentService, ServiceQuestion, ServiceQuestionAnswer
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
    GovernmentServiceSerializer,
    ServiceQuestionSerializer,
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    UserSerializer,
    RegistrationPaymentSerializer
)
from accounts.models import RegistrationPayment
import razorpay
import hmac
from .services.gemini_service import GeminiAIService
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
    serializer = UserLoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    phone = serializer.validated_data.get('phone', '').strip() if serializer.validated_data.get('phone') else None
    email = serializer.validated_data.get('email', '').strip() if serializer.validated_data.get('email') else None
    password = serializer.validated_data['password']
    
    # Authenticate user with phone or email
    user = authenticate(request, phone=phone, email=email, password=password)
    
    if user is None:
        return Response({
            'success': False,
            'message': 'Invalid credentials'
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
def create_payment_link(request):
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
    
    # if user.is_active:
    #     return Response({
    #         'success': False,
    #         'message': 'User account already activated'
    #     }, status=status.HTTP_400_BAD_REQUEST)
    
    if RegistrationPayment.objects.filter(user=user, status='SUCCESS').exists():
        return Response({
        'success': False,
        'message': 'Registration already completed. You are already subscribed.'
        }, status=status.HTTP_400_BAD_REQUEST)

    existing_payment = RegistrationPayment.objects.filter(
        user=user, 
        status='PENDING'
    ).first()
    
    if existing_payment and existing_payment.gateway_ref:
        # Return existing payment link
        payment_url = f"{settings.BASE_URL}/api/payments/registration/checkout/{existing_payment.id}"
        return Response({
            'success': True,
            'message': 'Payment link already exists',
            'payment_url': payment_url,
            'payment_id': existing_payment.id
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
        
        # Create payment record
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
        
        # Return payment URL that frontend can open
        payment_url = f"{settings.BASE_URL}/api/payments/registration/checkout/{payment.id}"
        
        return Response({
            'success': True,
            'message': 'Payment link created successfully',
            'payment_url': payment_url,
            'payment_id': payment.id
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Payment error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def payment_checkout(request, payment_id):
    try:
        payment = RegistrationPayment.objects.get(id=payment_id, status='PENDING')
        user = payment.user
        
        # if user.is_active:
        #     return render(request, 'payment_error.html', {
        #         'error_message': 'User account already activated',
        #         'frontend_url': settings.FRONTEND_URL
        #     })
        
        context = {
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'order_id': payment.gateway_ref,
            'amount': int(payment.amount * 100),  # Convert to paise
            'currency': 'INR',
            'user_name': user.name,
            'user_email': user.email or '',
            'user_phone': user.phone,
            'callback_url': f"{settings.BASE_URL}/api/payments/registration/callback",
            'payment_id': payment.id
        }
        
        return render(request, 'razorpay_checkout.html', context)
        
    except RegistrationPayment.DoesNotExist:
        return render(request, 'payment_error.html', {
            'error_message': 'Payment not found or already processed',
            'frontend_url': settings.FRONTEND_URL
        })


@csrf_exempt
def payment_callback(request):
    if request.method != 'POST':
        return render(request, 'payment_error.html', {
            'error_message': 'Invalid request method',
            'frontend_url': settings.FRONTEND_URL
        })
    
    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature = request.POST.get('razorpay_signature')
    
    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return render(request, 'payment_error.html', {
            'error_message': 'Missing payment details',
            'frontend_url': settings.FRONTEND_URL
        })
    
    try:
        # Verify signature
        generated_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature != razorpay_signature:
            return render(request, 'payment_failure.html', {
                'error_message': 'Payment verification failed',
                'frontend_url': settings.FRONTEND_URL
            })
        
        # Find payment record
        payment = RegistrationPayment.objects.filter(
            gateway_ref=razorpay_order_id,
            status='PENDING'
        ).first()
        
        if not payment:
            return render(request, 'payment_error.html', {
                'error_message': 'Payment record not found',
                'frontend_url': settings.FRONTEND_URL
            })
        
        user = payment.user
        
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
        
        return render(request, 'payment_success.html', {
            'user': user,
            'access_token': tokens['access'],
            'refresh_token': tokens['refresh'],
            'frontend_url': settings.FRONTEND_URL
        })
        
    except Exception as e:
        return render(request, 'payment_error.html', {
            'error_message': f'Error: {str(e)}',
            'frontend_url': settings.FRONTEND_URL
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def check_payment_status(request, payment_id):
    """
    Check payment status
    GET /api/payments/registration/status/<payment_id>
    """
    try:
        payment = RegistrationPayment.objects.get(id=payment_id)
        
        return Response({
            'success': True,
            'payment_id': payment.id,
            'status': payment.status,
            'user_id': payment.user.id,
            'user_active': payment.user.is_active,
            'amount': float(payment.amount),
            'created_at': payment.created_at,
            'updated_at': payment.updated_at
        }, status=status.HTTP_200_OK)
        
    except RegistrationPayment.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def get_ai_guide(request):
    question = request.data.get('question', '').strip()
    language = request.data.get('language', 'english').strip().lower()
    
    if not question:
        return Response({
            'success': False,
            'message': 'Question is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ai_service = GeminiAIService()
        result = ai_service.get_ai_guide(question, language)
        
        if not result['success']:
            return Response({
                'success': False,
                'message': result.get('message'),
                'error': result.get('error')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': 'Server error',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def government_service_api(request):
    if request.method == "GET":
        services = GovernmentService.objects.all()
        serializer = GovernmentServiceSerializer(services, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == "POST":
        service_id = request.data.get("service_id")

        if not service_id:
            return Response(
                {"error": "service_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not GovernmentService.objects.filter(id=service_id).exists():
            return Response(
                {"error": "Invalid service_id"},
                status=status.HTTP_404_NOT_FOUND
            )

        questions = ServiceQuestion.objects.filter(service_id=service_id)
        serializer = ServiceQuestionSerializer(questions, many=True)

        return Response(
            {
                "service_id": service_id,
                "questions": serializer.data
            },
            status=status.HTTP_200_OK
        )
    
@api_view(["GET"])
@permission_classes([AllowAny])
def service_question_answer_api(request):
    question_id = request.query_params.get("question_id")
    language = request.query_params.get("language", "english")  # default to english

    if not question_id:
        return Response(
            {"error": "question_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        answer = ServiceQuestionAnswer.objects.select_related(
            'question', 'question__service'
        ).get(question_id=question_id)
    except ServiceQuestionAnswer.DoesNotExist:
        return Response(
            {"error": "Answer not found for this question"},
            status=status.HTTP_404_NOT_FOUND
        )

    # Return answer based on language preference
    response_data = {
        "question_id": question_id,
        "question": answer.question.question,
        "service_name": answer.question.service.name,
        "answer": answer.answer_hindi if language.lower() == "hindi" else answer.answer_english,
        # "answer_english": answer.answer_english,
        # "answer_hindi": answer.answer_hindi
    }

    return Response(response_data, status=status.HTTP_200_OK)