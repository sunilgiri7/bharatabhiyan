from accounts.models import User
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import razorpay
import hmac
import hashlib
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from providers.models import (
    ServiceProvider, ServiceCategory, ServiceType,
    ServiceArea, ProviderSubscription
)
from django.shortcuts import get_object_or_404
from .provider_serializers import (
    ServiceProviderCreateSerializer, ServiceProviderUpdateSerializer,
    ServiceProviderDetailSerializer, ServiceProviderSubmitSerializer,
    ServiceCategorySerializer, ServiceTypeSerializer, ServiceAreaSerializer,
    ProviderSubscriptionSerializer, ProviderSubscriptionCreateSerializer, ServiceProviderListSerializer
)

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


# ===== Helper APIs for Dropdowns =====

@api_view(['GET'])
@permission_classes([AllowAny])
def get_service_categories(request):
    """Get all active service categories"""
    categories = ServiceCategory.objects.filter(is_active=True)
    serializer = ServiceCategorySerializer(categories, many=True)
    return Response({
        'success': True,
        'data': serializer.data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_service_types(request):
    category_ids = request.query_params.get('category_id')

    queryset = ServiceType.objects.filter(is_active=True)

    if category_ids:
        ids = [int(cid) for cid in category_ids.split(',') if cid.isdigit()]
        queryset = queryset.filter(category_id__in=ids)

    serializer = ServiceTypeSerializer(queryset, many=True)

    return Response({
        'success': True,
        'data': serializer.data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_service_areas(request):
    """Get service areas for a specific location"""
    location_id = request.query_params.get('location_id')
    
    if not location_id:
        return Response({
            'success': False,
            'message': 'location_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    service_areas = ServiceArea.objects.filter(
        location_id=location_id,
        is_active=True
    )
    serializer = ServiceAreaSerializer(service_areas, many=True)
    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def get_services(request):
    category_ids = request.query_params.get('categories', '').strip()
    service_type_ids = request.query_params.get('service_types', '').strip()
    
    # 1. Validate Category Input
    if not category_ids:
        return Response({
            'success': False,
            'message': 'categories parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        category_list = [int(id.strip()) for id in category_ids.split(',') if id.strip()]
    except ValueError:
        return Response({
            'success': False,
            'message': 'Invalid category IDs format'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 2. Logic: If Service Types provided -> Return PROVIDERS
    if service_type_ids:
        try:
            service_type_list = [int(id.strip()) for id in service_type_ids.split(',') if id.strip()]
        except ValueError:
            return Response({
                'success': False,
                'message': 'Invalid service_types format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # --- FIX: Use Many-to-Many lookup (plural field names) ---
        providers = ServiceProvider.objects.filter(
            service_categories__id__in=category_list, # Was: service_category_id
            service_types__id__in=service_type_list,  # Was: service_type_id
            verification_status='VERIFIED'            # NOTE: Only verified providers show up!
        ).select_related(
            'user', 
            'city'
        ).prefetch_related(
            'service_areas',
            'service_categories', # Prefetch M2M
            'service_types'       # Prefetch M2M
        ).distinct() # DISTINCT is vital for M2M filtering to avoid duplicates
        
        serializer = ServiceProviderListSerializer(providers, many=True, context={'request': request})
        
        return Response({
            'success': True,
            'data': {
                'providers': serializer.data,
                'count': providers.count()
            }
        })
    
    # 3. Logic: Only Categories provided -> Return SERVICE TYPES
    service_types = ServiceType.objects.filter(
        category_id__in=category_list,
        is_active=True
    ).select_related('category')
    
    serializer = ServiceTypeSerializer(service_types, many=True)
    return Response({
        'success': True,
        'data': {
            'service_types': serializer.data,
            'count': service_types.count()
        }
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def get_services_and_providers(request):
    category_ids = request.query_params.get('categories', '').strip()
    service_type_ids = request.query_params.get('service_types', '').strip()
    service_area_ids = request.query_params.get('service_areas', '').strip()

    def parse_ids(value, field_name):
        try:
            return [int(i.strip()) for i in value.split(',') if i.strip()]
        except ValueError:
            raise ValueError(f'Invalid {field_name} format')

    try:
        category_list = parse_ids(category_ids, 'categories') if category_ids else []
        service_type_list = parse_ids(service_type_ids, 'service_types') if service_type_ids else []
        service_area_list = parse_ids(service_area_ids, 'service_areas') if service_area_ids else []
    except ValueError as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    # 1. Logic: Only Categories Provided -> Return Service Types
    # (This part is fine as ServiceType still has a single Foreign Key to Category)
    if category_list and not service_type_list and not service_area_list:
        service_types = ServiceType.objects.filter(
            category_id__in=category_list,
            is_active=True
        ).select_related('category')

        serializer = ServiceTypeSerializer(service_types, many=True)

        return Response({
            'success': True,
            'data': {
                'service_types': serializer.data,
                'count': service_types.count()
            }
        })

    # 2. Validation: Ensure at least one filter exists
    # if not (category_list or service_type_list or service_area_list):
    #     return Response({
    #         'success': False,
    #         'message': 'At least one of categories, service_types or service_areas is required'
    #     }, status=status.HTTP_400_BAD_REQUEST)

    # 3. Build Filters for Providers
    filters = Q(verification_status='VERIFIED')

    # FIX: Updated Lookups for Many-to-Many (Use plural field names)
    if category_list:
        # Check if provider has any of these categories
        filters &= Q(service_categories__id__in=category_list)
        
        # Optional: Ensure the provider's service types also belong to these categories
        # Note: 'service_types' is the M2M field name on Provider
        filters &= Q(service_types__category__id__in=category_list)

    if service_type_list:
        # Check if provider offers any of these specific service types
        filters &= Q(service_types__id__in=service_type_list)

    if service_area_list:
        filters &= Q(service_areas__id__in=service_area_list)

    # 4. Fetch Providers (Optimized)
    # FIX: Removed 'service_category'/'service_type' from select_related (they are lists now)
    # FIX: Added them to prefetch_related
    providers = ServiceProvider.objects.filter(filters).distinct().select_related(
        'user', 'city'
    ).prefetch_related(
        'service_areas',
        'service_categories', # Prefetch the categories list
        'service_types'       # Prefetch the types list
    )

    serializer = ServiceProviderListSerializer(
        providers,
        many=True,
        context={'request': request}
    )

    return Response({
        'success': True,
        'data': {
            'providers': serializer.data,
            'count': providers.count()
        }
    })


# ===== Provider Registration APIs =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def create_or_update_provider_profile(request):
    """Create or update service provider profile (draft)"""

    user = request.user

    # Account must be active
    if not user.is_active:
        return Response({
            'success': False,
            'message': 'Your account must be activated before registering as a provider'
        }, status=status.HTTP_400_BAD_REQUEST)

    provider = getattr(user, 'provider_profile', None)

    if provider:
        # UPDATE
        serializer = ServiceProviderUpdateSerializer(
            provider,
            data=request.data,
            context={'request': request},
            partial=True
        )
        status_code = status.HTTP_200_OK
        success_message = 'Provider profile updated successfully'
    else:
        # CREATE
        serializer = ServiceProviderCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        status_code = status.HTTP_201_CREATED
        success_message = 'Provider profile created successfully'

    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    provider = serializer.save()

    detail_serializer = ServiceProviderDetailSerializer(
        provider,
        context={'request': request}
    )

    return Response({
        'success': True,
        'message': success_message,
        'data': detail_serializer.data
    }, status=status_code)

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def get_provider_profile(request):

    if request.method == 'GET':
        try:
            provider = request.user.provider_profile
        except ServiceProvider.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Provider profile not found'
            }, status=status.HTTP_404_NOT_FOUND)

    else:  # POST
        provider_id = request.data.get('user_id')

        if not provider_id:
            return Response({
                'success': False,
                'message': 'provider_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            provider = ServiceProvider.objects.get(id=provider_id)
        except ServiceProvider.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Provider not found'
            }, status=status.HTTP_404_NOT_FOUND)

    serializer = ServiceProviderDetailSerializer(provider)

    return Response({
        'success': True,
        'data': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_provider_application(request):
    """Submit provider application for captain verification"""

    user = request.user

    try:
        provider = user.provider_profile
    except ServiceProvider.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Provider profile not found. Please create your profile first.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 🔄 Always work with the latest data (critical after draft updates)
    provider.refresh_from_db()

    # 🚫 Prevent duplicate submissions
    if provider.verification_status not in ['DRAFT', 'REJECTED']:
        return Response({
            'success': False,
            'message': f'Application already {provider.verification_status.lower()}'
        }, status=status.HTTP_400_BAD_REQUEST)

    # ✅ Validate declarations
    serializer = ServiceProviderSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': 'All declarations must be accepted',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    # 📋 Required field validation (UPDATED for M2M fields)
    required_fields = [
        'whatsapp_number',
        'business_name',
        'experience',
        'business_address',
        'city',
        'pincode',
        'service_categories',
        'service_types',
        'service_description',
        'aadhaar_front',
        'aadhaar_back',
        'address_proof_type',
        'address_proof',
        'profile_photo',
    ]

    missing_fields = []

    for field in required_fields:
        # Handle ManyToMany fields correctly
        if field in ['service_categories', 'service_types', 'service_areas']:
            if not getattr(provider, field).exists():
                missing_fields.append(field.replace('_', ' ').title())
            continue

        value = getattr(provider, field, None)
        if not value:
            missing_fields.append(field.replace('_', ' ').title())

    if missing_fields:
        return Response({
            'success': False,
            'message': 'Please complete all required fields',
            'missing_fields': missing_fields
        }, status=status.HTTP_400_BAD_REQUEST)

    if not provider.service_areas.exists():
        return Response({
            'success': False,
            'message': 'Please select at least one service area'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 🚀 Submit for verification
    provider.verification_status = 'PENDING_VERIFICATION'
    provider.submitted_at = timezone.now()
    provider.rejection_reason = ''
    provider.save()

    detail_serializer = ServiceProviderDetailSerializer(
        provider,
        context={'request': request}
    )

    return Response({
        'success': True,
        'message': 'Application submitted successfully. A captain will verify your details within 2-3 business days.',
        'data': detail_serializer.data
    }, status=status.HTTP_200_OK)


# ===== Subscription & Payment APIs =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_subscription_payment(request):
    """Create payment link for provider subscription"""
    user = request.user
    
    # Validate provider profile
    try:
        provider = user.provider_profile
        if provider.verification_status != 'VERIFIED':
            return Response({
                'success': False,
                'message': 'Your provider profile must be verified first'
            }, status=status.HTTP_400_BAD_REQUEST)
    except ServiceProvider.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Provider profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Validate plan type
    serializer = ProviderSubscriptionCreateSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if not serializer.is_valid():
        errors = serializer.errors

        if 'message' in errors:
            return Response({
                'success': False,
                'message': errors['message'][0],
                'subscription_id': errors.get('subscription_id', [None])[0]
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    plan_type = serializer.validated_data['plan_type']
    
    # Calculate amount and slots
    if plan_type == 'MONTHLY':
        amount = 199.00
        listing_slots = 1
    else:  # YEARLY
        amount = 1499.00
        listing_slots = 3
    
    # Add GST (18%)
    gst_amount = amount * 0.18
    total_amount = amount + gst_amount
    
    try:
        # Create Razorpay Order
        razorpay_order = razorpay_client.order.create({
            'amount': int(total_amount * 100),  # Convert to paise
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'provider_id': str(provider.id),
                'plan_type': plan_type,
                'payment_type': 'provider_subscription'
            }
        })
        
        # Create subscription record
        subscription = ProviderSubscription.objects.create(
            provider=provider,
            plan_type=plan_type,
            amount=total_amount,
            listing_slots=listing_slots,
            status='PENDING',
            gateway_order_id=razorpay_order['id']
        )
        
        # Return payment checkout URL
        payment_url = f"{settings.BASE_URL}/api/providers/subscription/checkout/{subscription.id}"
        
        return Response({
            'success': True,
            'message': 'Payment link created successfully',
            'data': {
                'subscription_id': subscription.id,
                'payment_url': payment_url,
                'plan_type': plan_type,
                'amount': float(amount),
                'gst': float(gst_amount),
                'total_amount': float(total_amount),
                'listing_slots': listing_slots
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Payment error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def subscription_payment_checkout(request, subscription_id):
    """Render Razorpay checkout page for subscription"""
    try:
        subscription = ProviderSubscription.objects.get(
            id=subscription_id,
            status='PENDING'
        )
        provider = subscription.provider
        user = provider.user
        
        context = {
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'order_id': subscription.gateway_order_id,
            'amount': int(subscription.amount * 100),  # Convert to paise
            'currency': 'INR',
            'user_name': user.name,
            'user_email': user.email or '',
            'user_phone': user.phone,
            'callback_url': f"{settings.BASE_URL}/api/providers/subscription/callback",
            'subscription_id': subscription.id,
            'plan_type': subscription.get_plan_type_display(),
        }
        
        return render(request, 'razorpay_checkout.html', context)
        
    except ProviderSubscription.DoesNotExist:
        return render(request, 'payment_error.html', {
            'error_message': 'Subscription not found or already processed',
            'frontend_url': settings.FRONTEND_URL
        })


@csrf_exempt
def subscription_payment_callback(request):
    """Handle Razorpay payment callback for subscription"""
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
        
        # Find subscription record
        subscription = ProviderSubscription.objects.filter(
            gateway_order_id=razorpay_order_id,
            status='PENDING'
        ).first()
        
        if not subscription:
            return render(request, 'payment_error.html', {
                'error_message': 'Subscription record not found',
                'frontend_url': settings.FRONTEND_URL
            })
        
        # Update subscription status
        subscription.status = 'ACTIVE'
        subscription.gateway_payment_id = razorpay_payment_id
        subscription.start_date = timezone.now()
        
        # Calculate end date
        if subscription.plan_type == 'MONTHLY':
            subscription.end_date = subscription.start_date + relativedelta(months=1)
        else:  # YEARLY
            subscription.end_date = subscription.start_date + relativedelta(years=1)
        
        subscription.save()
        
        provider = subscription.provider
        
        return render(request, 'subscription_success.html', {
            'provider': provider,
            'subscription': subscription,
            'frontend_url': settings.FRONTEND_URL
        })
        
    except Exception as e:
        return render(request, 'payment_error.html', {
            'error_message': f'Error: {str(e)}',
            'frontend_url': settings.FRONTEND_URL
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_subscription_status(request, subscription_id):
    """Check subscription payment status"""
    user = request.user
    
    try:
        provider = user.provider_profile
        subscription = ProviderSubscription.objects.get(
            id=subscription_id,
            provider=provider
        )
        
        serializer = ProviderSubscriptionSerializer(subscription)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
        
    except ServiceProvider.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Provider profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except ProviderSubscription.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Subscription not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_subscription(request):
    """Get user's active subscription"""
    user = request.user
    
    try:
        provider = user.provider_profile
        subscription = ProviderSubscription.objects.filter(
            provider=provider,
            status='ACTIVE',
            end_date__gte=timezone.now()
        ).order_by('-created_at').first()
        
        if subscription:
            serializer = ProviderSubscriptionSerializer(subscription)
            return Response({
                'success': True,
                'data': serializer.data
            })
        else:
            return Response({
                'success': False,
                'message': 'No active subscription found'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except ServiceProvider.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Provider profile not found'
        }, status=status.HTTP_404_NOT_FOUND)