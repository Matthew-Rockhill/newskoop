# accounts/views.py
import logging
from rest_framework import status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from .models import RadioStation, CustomUser
from .serializers import (
    UserSerializer, 
    RadioStationSerializer,
    RadioUserCreateSerializer,
    RadioUserUpdateSerializer
    # other existing serializers
)

User = get_user_model()
logger = logging.getLogger(__name__)

class LoginView(APIView):
    """
    Login view that accepts email and password and returns JWT tokens
    """
    permission_classes = [permissions.AllowAny]
    
# In accounts/views.py, enhance the LoginView post method

def post(self, request):
    email = request.data.get('email')
    password = request.data.get('password')
    
    # More detailed validation
    errors = {}
    if not email:
        errors['email'] = 'Email is required'
    if not password:
        errors['password'] = 'Password is required'
    
    if errors:
        logger.warning(f"Login attempt with missing credentials: {', '.join(errors.keys())}")
        return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, username=email, password=password)
    
    if user:
        if not user.is_active:
            logger.warning(f"Login attempt by inactive user: {email}")
            return Response({'error': 'Account is inactive'}, status=status.HTTP_403_FORBIDDEN)
        
        refresh = RefreshToken.for_user(user)
        logger.info(f"User login successful: {user.email}")
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        })
    
    logger.warning(f"Failed login attempt for email: {email}")
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(APIView):
    """
    Logout view that blacklists the refresh token
    """
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                logger.warning(f"Logout attempt without refresh token")
                return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
                
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"User logged out: {request.user.email}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({'error': 'Something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserProfileView(APIView):
    """
    View for getting and updating user profile
    """
    def get(self, request):
        serializer = UserSerializer(request.user)
        logger.info(f"User profile accessed: {request.user.email}")
        return Response(serializer.data)
    
    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"User profile updated: {request.user.email}")
            return Response(serializer.data)
        logger.warning(f"User profile update failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AdminPermission(permissions.BasePermission):
    """Permission class to check if user is an admin"""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.user_type == CustomUser.UserType.STAFF and
            request.user.staff_role in [CustomUser.StaffRole.SUPERADMIN, CustomUser.StaffRole.ADMIN]
        )


class RadioStationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing radio stations"""
    queryset = RadioStation.objects.all().order_by('name')
    serializer_class = RadioStationSerializer
    permission_classes = [AdminPermission]
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users for a specific radio station"""
        station = self.get_object()
        users = station.users.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_user(self, request, pk=None):
        """Add a new user to a radio station"""
        station = self.get_object()
        
        # Inject the station into the request data
        data = request.data.copy()
        data['radio_station'] = station.id
        
        serializer = RadioUserCreateSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def set_primary_contact(self, request, pk=None):
        """Set a user as the primary contact for a radio station"""
        station = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {"error": "User ID is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Find the user
            user = station.users.get(id=user_id)
            
            # Use transaction to ensure atomicity
            from django.db import transaction
            with transaction.atomic():
                # Reset any existing primary contacts
                station.users.filter(is_primary_contact=True).update(is_primary_contact=False)
                
                # Set this user as primary
                user.is_primary_contact = True
                user.save()
            
            return Response({"success": "Primary contact updated"})
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found in this station"}, 
                status=status.HTTP_404_NOT_FOUND
            )