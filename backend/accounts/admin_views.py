# accounts/admin_views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import RadioStation
from .serializers import (
    UserSerializer, 
    StaffUserCreateSerializer,
    StaffUserUpdateSerializer,
    RadioUserCreateSerializer,
    RadioUserUpdateSerializer
)
from .views import AdminPermission

User = get_user_model()

@api_view(['GET'])
@permission_classes([AdminPermission])
def system_stats(request):
    """Provide system statistics for admin dashboard"""
    stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'staff_users': User.objects.filter(user_type=User.UserType.STAFF).count(),
        'radio_users': User.objects.filter(user_type=User.UserType.RADIO).count(),
        'active_stations': RadioStation.objects.filter(is_active=True).count(),
        'total_stations': RadioStation.objects.count(),
        # Add other relevant stats
    }
    return Response(stats)

class AdminUserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing all users via admin interface"""
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [AdminPermission]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action and user type"""
        if self.action == 'create':
            # For create action, determine which serializer to use based on request data
            user_type = self.request.data.get('user_type', '').upper()
            if user_type == User.UserType.RADIO:
                return RadioUserCreateSerializer
            else:
                return StaffUserCreateSerializer
        
        elif self.action == 'update' or self.action == 'partial_update':
            # For update actions, determine serializer based on user type of the instance
            instance = self.get_object()
            if instance.user_type == User.UserType.RADIO:
                return RadioUserUpdateSerializer
            else:
                return StaffUserUpdateSerializer
            
        return super().get_serializer_class()
    
    def get_queryset(self):
        """Filter users based on query parameters"""
        queryset = User.objects.all().order_by('-date_joined')
        
        # Filter by user type
        user_type = self.request.query_params.get('user_type')
        if user_type:
            queryset = queryset.filter(user_type=user_type.upper())
        
        # Filter by radio station
        station_id = self.request.query_params.get('station_id')
        if station_id:
            queryset = queryset.filter(radio_station_id=station_id)
            
        # Filter by staff role
        staff_role = self.request.query_params.get('staff_role')
        if staff_role:
            queryset = queryset.filter(staff_role=staff_role.upper())
            
        return queryset
    
    def list(self, request, *args, **kwargs):
        """Override list method to include pagination and total count info"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get total count before pagination
        total_count = queryset.count()
        
        # Use pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            # Add total count to response
            response.data['total_count'] = total_count
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'total_count': total_count
        })
    
    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """Reset a user's password (admin only)"""
        user = self.get_object()
        password = request.data.get('password')
        
        if not password:
            return Response(
                {"error": "Password is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(password)
        user.save()
        
        return Response({"success": "Password has been reset"})
    
    @action(detail=True, methods=['post'])
    def set_active(self, request, pk=None):
        """Set a user's active status"""
        user = self.get_object()
        is_active = request.data.get('is_active')
        
        if is_active is None:
            return Response(
                {"error": "is_active field is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.is_active = is_active
        user.save()
        
        return Response({"success": "User status updated"})
    
    @action(detail=False, methods=['get'])
    def staff(self, request):
        """Get all staff users"""
        queryset = self.get_queryset().filter(user_type=User.UserType.STAFF)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def radio(self, request):
        """Get all radio station users"""
        queryset = self.get_queryset().filter(user_type=User.UserType.RADIO)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)