from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class PhoneBackend(ModelBackend):
    """
    Custom authentication backend to allow login with phone number or email
    """
    def authenticate(self, request, phone=None, email=None, password=None, **kwargs):
        if password is None:
            return None
        
        user = None
        
        # Try to authenticate with phone
        if phone:
            try:
                user = User.objects.get(phone=phone)
            except User.DoesNotExist:
                pass
        
        # Try to authenticate with email
        if not user and email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass
        
        if user and user.check_password(password):
            return user
        
        return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None