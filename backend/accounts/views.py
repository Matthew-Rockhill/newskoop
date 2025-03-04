# accounts/views.py
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from rest_framework import status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

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

# =============== API VIEWS ===============

class LoginView(APIView):
    """
    API Login view that accepts email and password and returns JWT tokens
    """
    permission_classes = [permissions.AllowAny]
    
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
            logger.warning(f"API login attempt with missing credentials: {', '.join(errors.keys())}")
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
        
        user = authenticate(request, username=email, password=password)
        
        if user:
            if not user.is_active:
                logger.warning(f"API login attempt by inactive user: {email}")
                return Response({'error': 'Account is inactive'}, status=status.HTTP_403_FORBIDDEN)
            
            refresh = RefreshToken.for_user(user)
            logger.info(f"API user login successful: {user.email}")
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            })
        
        logger.warning(f"Failed API login attempt for email: {email}")
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """
    API Logout view that blacklists the refresh token
    """
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                logger.warning(f"API logout attempt without refresh token")
                return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
                
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"API user logged out: {request.user.email}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"API logout error: {str(e)}")
            return Response({'error': 'Something went wrong'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserProfileView(APIView):
    """
    API View for getting and updating user profile
    """
    def get(self, request):
        serializer = UserSerializer(request.user)
        logger.info(f"API user profile accessed: {request.user.email}")
        return Response(serializer.data)
    
    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"API user profile updated: {request.user.email}")
            return Response(serializer.data)
        logger.warning(f"API user profile update failed: {serializer.errors}")
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


# =============== TEMPLATE VIEWS (NEW) ===============

class LoginPageView(APIView):
    """View for handling user login with templates"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        # If user is already authenticated, redirect to dashboard
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        return render(request, 'accounts/login.html')
    
    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Basic validation
        errors = {}
        if not email:
            errors['email'] = 'Email is required'
        if not password:
            errors['password'] = 'Password is required'
        
        if errors:
            for field, error in errors.items():
                messages.error(request, error)
            return render(request, 'accounts/login.html')
        
        # Attempt to authenticate
        user = authenticate(request, username=email, password=password)
        
        if user:
            if not user.is_active:
                logger.warning(f"Login attempt by inactive user: {email}")
                messages.warning(request, 'Your account is inactive. Please contact an administrator.')
                return render(request, 'accounts/login.html')
            
            # Log the user in using Django's session-based authentication
            django_login(request, user)
            logger.info(f"User login successful: {user.email}")
            
            # Redirect to appropriate page
            return redirect('dashboard')
        
        # Authentication failed
        logger.warning(f"Failed login attempt for email: {email}")
        messages.error(request, 'Invalid email or password.')
        return render(request, 'accounts/login.html')


@require_http_methods(["POST"])
def logout_view(request):
    """Handle user logout (template-based)"""
    if request.user.is_authenticated:
        logger.info(f"User logged out: {request.user.email}")
    
    django_logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


@login_required
def dashboard_view(request):
    """Dashboard view for authenticated users"""
    user = request.user
    context = {}
    
    # Get user-specific stats and activities
    if user.user_type == CustomUser.UserType.STAFF:
        # Admin dashboard stats
        stats = {
            'active_users': CustomUser.objects.filter(is_active=True).count(),
            'active_stations': RadioStation.objects.filter(is_active=True).count(),
            'content_count': 0,  # Will be populated once newsroom models are added
        }
        
        # Mock recent activity for now
        recent_activity = [
            {
                'type': 'user',
                'text': 'New user "john@example.com" was created',
                'time': '2 hours ago'
            },
            {
                'type': 'station',
                'text': 'Radio station "Community FM" was updated',
                'time': '3 hours ago'
            },
            {
                'type': 'content',
                'text': 'New bulletin "Morning News" was published',
                'time': '5 hours ago'
            }
        ]
    else:
        # Radio user dashboard stats
        stats = {
            'available_content': 0,  # Will be populated once radio_zone models are added
            'downloads': 0,
            'new_updates': 0
        }
        
        # Mock recent activity for radio users
        recent_activity = [
            {
                'type': 'content',
                'text': 'New content is available for your station',
                'time': '1 hour ago'
            },
            {
                'type': 'station',
                'text': 'Your station details were updated',
                'time': '1 day ago'
            }
        ]
    
    context['stats'] = stats
    context['recent_activity'] = recent_activity
    
    return render(request, 'dashboard.html', context)


@login_required
def profile_view(request):
    """View function for user profile page"""
    user = request.user
    
    if request.method == 'POST':
        # Handle profile updates
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        mobile_number = request.POST.get('mobile_number')
        
        # Update user object
        user.first_name = first_name
        user.last_name = last_name
        user.mobile_number = mobile_number
        user.save()
        
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    
    return render(request, 'accounts/profile.html', {'user': user})

# Helper function to check if user is an admin
def is_admin(user):
    return (user.is_authenticated and 
            user.user_type == CustomUser.UserType.STAFF and
            user.staff_role in [CustomUser.StaffRole.SUPERADMIN, CustomUser.StaffRole.ADMIN])

# Decorator for admin-only views
def admin_required(view_func):
    decorated_view = user_passes_test(is_admin)(view_func)
    return decorated_view

# =============== RADIO STATION MANAGEMENT VIEWS ===============

@login_required
@admin_required
def station_list(request):
    """View for listing all radio stations"""
    stations = RadioStation.objects.all().order_by('name')
    
    # Handle search
    search_query = request.GET.get('q')
    if search_query:
        stations = stations.filter(name__icontains=search_query)
    
    # Handle filters
    province_filter = request.GET.get('province')
    if province_filter:
        stations = stations.filter(province=province_filter)
        
    status_filter = request.GET.get('status')
    if status_filter:
        is_active = status_filter == 'active'
        stations = stations.filter(is_active=is_active)
    
    return render(request, 'accounts/stations/list.html', {
        'stations': stations,
        'search_query': search_query,
        'province_filter': province_filter,
        'status_filter': status_filter,
        'provinces': RadioStation.Province.choices,
    })

@login_required
@admin_required
def station_create(request):
    """View for creating a new radio station"""
    if request.method == 'POST':
        # Extract form data for station
        name = request.POST.get('name')
        description = request.POST.get('description')
        province = request.POST.get('province')
        contact_number = request.POST.get('contact_number')
        contact_email = request.POST.get('contact_email')
        website = request.POST.get('website')
        is_active = request.POST.get('is_active') == 'on'
        
        # Extract access settings
        religion_access = request.POST.get('religion_access')
        access_english = request.POST.get('access_english') == 'on'
        access_afrikaans = request.POST.get('access_afrikaans') == 'on'
        access_xhosa = request.POST.get('access_xhosa') == 'on'
        access_news_stories = request.POST.get('access_news_stories') == 'on'
        access_news_bulletins = request.POST.get('access_news_bulletins') == 'on'
        access_sport = request.POST.get('access_sport') == 'on'
        access_finance = request.POST.get('access_finance') == 'on'
        access_specialty = request.POST.get('access_specialty') == 'on'
        
        # Extract primary contact details
        primary_contact_email = request.POST.get('primary_contact_email')
        primary_contact_password = request.POST.get('primary_contact_password')
        primary_contact_first_name = request.POST.get('primary_contact_first_name')
        primary_contact_last_name = request.POST.get('primary_contact_last_name')
        primary_contact_mobile = request.POST.get('primary_contact_mobile')
        
        # Basic validation
        if not name:
            messages.error(request, 'Station name is required.')
            return render(request, 'accounts/stations/create.html', {
                'provinces': RadioStation.Province.choices,
                'religion_choices': RadioStation.RELIGION_CHOICES,
            })
        
        # Validate primary contact details if provided
        if primary_contact_email and not primary_contact_password:
            messages.error(request, 'Password is required for primary contact.')
            return render(request, 'accounts/stations/create.html', {
                'provinces': RadioStation.Province.choices,
                'religion_choices': RadioStation.RELIGION_CHOICES,
            })
        
        # Check if user with this email already exists
        if primary_contact_email and CustomUser.objects.filter(email=primary_contact_email).exists():
            messages.error(request, f'A user with email "{primary_contact_email}" already exists.')
            return render(request, 'accounts/stations/create.html', {
                'provinces': RadioStation.Province.choices,
                'religion_choices': RadioStation.RELIGION_CHOICES,
            })
        
        # Create the station and primary contact user if details provided
        try:
            from django.db import transaction
            with transaction.atomic():
                # Create the station
                station = RadioStation.objects.create(
                    name=name,
                    description=description,
                    province=province,
                    contact_number=contact_number,
                    contact_email=contact_email,
                    website=website,
                    is_active=is_active,
                    religion_access=religion_access,
                    access_english=access_english,
                    access_afrikaans=access_afrikaans,
                    access_xhosa=access_xhosa,
                    access_news_stories=access_news_stories,
                    access_news_bulletins=access_news_bulletins,
                    access_sport=access_sport,
                    access_finance=access_finance,
                    access_specialty=access_specialty
                )
                
                # Create primary contact user if details were provided
                if primary_contact_email and primary_contact_password:
                    CustomUser.objects.create_user(
                        email=primary_contact_email,
                        password=primary_contact_password,
                        first_name=primary_contact_first_name,
                        last_name=primary_contact_last_name,
                        mobile_number=primary_contact_mobile,
                        user_type=CustomUser.UserType.RADIO,
                        radio_station=station,
                        is_primary_contact=True,
                        is_active=is_active  # Same status as the station
                    )
                    messages.success(request, f'Radio station "{name}" has been created with primary contact user.')
                else:
                    messages.success(request, f'Radio station "{name}" has been created. You can add users later.')
                
                return redirect('station_detail', station_id=station.id)
        
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show the form
    return render(request, 'accounts/stations/create.html', {
        'provinces': RadioStation.Province.choices,
        'religion_choices': RadioStation.RELIGION_CHOICES,
    })

@login_required
@admin_required
def station_edit(request, station_id):
    """View for editing an existing radio station"""
    station = get_object_or_404(RadioStation, id=station_id)
    
    if request.method == 'POST':
        # Extract form data
        name = request.POST.get('name')
        description = request.POST.get('description')
        province = request.POST.get('province')
        contact_number = request.POST.get('contact_number')
        contact_email = request.POST.get('contact_email')
        website = request.POST.get('website')
        is_active = request.POST.get('is_active') == 'on'
        
        # Extract access settings
        religion_access = request.POST.get('religion_access')
        access_english = request.POST.get('access_english') == 'on'
        access_afrikaans = request.POST.get('access_afrikaans') == 'on'
        access_xhosa = request.POST.get('access_xhosa') == 'on'
        access_news_stories = request.POST.get('access_news_stories') == 'on'
        access_news_bulletins = request.POST.get('access_news_bulletins') == 'on'
        access_sport = request.POST.get('access_sport') == 'on'
        access_finance = request.POST.get('access_finance') == 'on'
        access_specialty = request.POST.get('access_specialty') == 'on'
        
        # Basic validation
        if not name:
            messages.error(request, 'Station name is required.')
            return render(request, 'accounts/stations/edit.html', {
                'station': station,
                'provinces': RadioStation.Province.choices,
                'religion_choices': RadioStation.RELIGION_CHOICES,
            })
        
        # Update the station
        try:
            # Save previous active state to check for changes
            was_active = station.is_active
            
            station.name = name
            station.description = description
            station.province = province
            station.contact_number = contact_number
            station.contact_email = contact_email
            station.website = website
            station.is_active = is_active
            station.religion_access = religion_access
            station.access_english = access_english
            station.access_afrikaans = access_afrikaans
            station.access_xhosa = access_xhosa
            station.access_news_stories = access_news_stories
            station.access_news_bulletins = access_news_bulletins
            station.access_sport = access_sport
            station.access_finance = access_finance
            station.access_specialty = access_specialty
            
            station.save()
            
            messages.success(request, f'Radio station "{name}" has been updated.')
            return redirect('station_detail', station_id=station.id)
        
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show the form with current data
    return render(request, 'accounts/stations/edit.html', {
        'station': station,
        'provinces': RadioStation.Province.choices,
        'religion_choices': RadioStation.RELIGION_CHOICES,
    })

@login_required
@admin_required
def station_detail(request, station_id):
    """View for showing station details"""
    station = get_object_or_404(RadioStation, id=station_id)
    station_users = station.users.all().order_by('-is_primary_contact', 'email')
    
    return render(request, 'accounts/stations/detail.html', {
        'station': station,
        'users': station_users,
    })

@login_required
@admin_required
def station_delete(request, station_id):
    """View for deleting a radio station"""
    station = get_object_or_404(RadioStation, id=station_id)
    
    if request.method == 'POST':
        name = station.name
        station.delete()
        messages.success(request, f'Radio station "{name}" has been deleted.')
        return redirect('station_list')
    
    return render(request, 'accounts/stations/delete_confirm.html', {
        'station': station,
    })

@login_required
@admin_required
def station_user_list(request, station_id):
    """View for listing all users of a radio station"""
    station = get_object_or_404(RadioStation, id=station_id)
    users = station.users.all().order_by('-is_primary_contact', 'email')
    
    return render(request, 'accounts/stations/user_list.html', {
        'station': station,
        'users': users,
    })

@login_required
@admin_required
def station_add_user(request, station_id):
    """View for adding a user to a radio station"""
    station = get_object_or_404(RadioStation, id=station_id)
    
    if request.method == 'POST':
        # Extract form data
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        mobile_number = request.POST.get('mobile_number')
        is_primary_contact = request.POST.get('is_primary_contact') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        # Basic validation
        if not email or not password:
            messages.error(request, 'Email and password are required.')
            return render(request, 'accounts/stations/add_user.html', {
                'station': station,
            })
        
        # Check if user with this email already exists
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, f'A user with email "{email}" already exists.')
            return render(request, 'accounts/stations/add_user.html', {
                'station': station,
            })
        
        # Check if there's already a primary contact
        if is_primary_contact and station.users.filter(is_primary_contact=True).exists():
            # Get the existing primary contact
            existing_primary = station.users.get(is_primary_contact=True)
            # Update the existing primary contact
            existing_primary.is_primary_contact = False
            existing_primary.save()
        
        # Create the user
        try:
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                mobile_number=mobile_number,
                user_type=CustomUser.UserType.RADIO,
                radio_station=station,
                is_primary_contact=is_primary_contact,
                is_active=is_active
            )
            
            messages.success(request, f'User "{email}" has been added to the station.')
            return redirect('station_user_list', station_id=station.id)
        
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show the form
    return render(request, 'accounts/stations/add_user.html', {
        'station': station,
    })

@login_required
@admin_required
def set_primary_contact(request, station_id, user_id):
    """AJAX view for setting a user as the primary contact for a station"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        station = get_object_or_404(RadioStation, id=station_id)
        user = get_object_or_404(CustomUser, id=user_id, radio_station=station)
        
        # Reset any existing primary contacts
        station.users.filter(is_primary_contact=True).update(is_primary_contact=False)
        
        # Set this user as primary
        user.is_primary_contact = True
        user.save()
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
    # =============== USER MANAGEMENT VIEWS ===============

@login_required
@admin_required
def user_list(request):
    """View for listing all users"""
    # Default to staff users
    user_type = request.GET.get('user_type', CustomUser.UserType.STAFF)
    users = CustomUser.objects.filter(user_type=user_type).order_by('email')
    
    # Handle search
    search_query = request.GET.get('q')
    if search_query:
        users = users.filter(email__icontains=search_query)
    
    # Handle filters
    if user_type == CustomUser.UserType.STAFF:
        role_filter = request.GET.get('role')
        if role_filter:
            users = users.filter(staff_role=role_filter)
    else:  # RADIO users
        station_filter = request.GET.get('station')
        if station_filter:
            users = users.filter(radio_station_id=station_filter)
    
    status_filter = request.GET.get('status')
    if status_filter:
        is_active = status_filter == 'active'
        users = users.filter(is_active=is_active)
    
    # Get stations for filtering radio users
    stations = None
    if user_type == CustomUser.UserType.RADIO:
        stations = RadioStation.objects.all().order_by('name')
    
    return render(request, 'accounts/users/list.html', {
        'users': users,
        'search_query': search_query,
        'user_type': user_type,
        'staff_roles': CustomUser.StaffRole.choices,
        'role_filter': role_filter if 'role_filter' in locals() else None,
        'stations': stations,
        'station_filter': station_filter if 'station_filter' in locals() else None,
        'status_filter': status_filter,
    })

@login_required
@admin_required
def create_staff_user(request):
    """View for creating a new staff user"""
    if request.method == 'POST':
        # Extract form data
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        mobile_number = request.POST.get('mobile_number')
        staff_role = request.POST.get('staff_role')
        is_active = request.POST.get('is_active') == 'on'
        
        # Basic validation
        if not email or not password:
            messages.error(request, 'Email and password are required.')
            return render(request, 'accounts/users/create_staff.html', {
                'staff_roles': CustomUser.StaffRole.choices,
            })
        
        # Check if user with this email already exists
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, f'A user with email "{email}" already exists.')
            return render(request, 'accounts/users/create_staff.html', {
                'staff_roles': CustomUser.StaffRole.choices,
            })
        
        # Create the user
        try:
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                mobile_number=mobile_number,
                user_type=CustomUser.UserType.STAFF,
                staff_role=staff_role,
                is_active=is_active
            )
            
            messages.success(request, f'Staff user "{email}" has been created.')
            return redirect('user_list')
        
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show the form
    return render(request, 'accounts/users/create_staff.html', {
        'staff_roles': CustomUser.StaffRole.choices,
    })

@login_required
@admin_required
def create_radio_user(request):
    """View for creating a new radio station user"""
    if request.method == 'POST':
        # Extract form data
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        mobile_number = request.POST.get('mobile_number')
        radio_station_id = request.POST.get('radio_station')
        is_primary_contact = request.POST.get('is_primary_contact') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        # Basic validation
        if not email or not password or not radio_station_id:
            messages.error(request, 'Email, password, and radio station are required.')
            return render(request, 'accounts/users/create_radio.html', {
                'stations': RadioStation.objects.all().order_by('name'),
            })
        
        # Check if user with this email already exists
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, f'A user with email "{email}" already exists.')
            return render(request, 'accounts/users/create_radio.html', {
                'stations': RadioStation.objects.all().order_by('name'),
            })
        
        # Get the radio station
        try:
            station = RadioStation.objects.get(id=radio_station_id)
        except RadioStation.DoesNotExist:
            messages.error(request, 'Selected radio station does not exist.')
            return render(request, 'accounts/users/create_radio.html', {
                'stations': RadioStation.objects.all().order_by('name'),
            })
        
        # Check if there's already a primary contact
        if is_primary_contact and station.users.filter(is_primary_contact=True).exists():
            # Get the existing primary contact
            existing_primary = station.users.get(is_primary_contact=True)
            # Update the existing primary contact
            existing_primary.is_primary_contact = False
            existing_primary.save()
        
        # Create the user
        try:
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                mobile_number=mobile_number,
                user_type=CustomUser.UserType.RADIO,
                radio_station=station,
                is_primary_contact=is_primary_contact,
                is_active=is_active
            )
            
            messages.success(request, f'Radio user "{email}" has been created.')
            return redirect('user_list')
        
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show the form
    return render(request, 'accounts/users/create_radio.html', {
        'stations': RadioStation.objects.all().order_by('name'),
    })

@login_required
@admin_required
def edit_user(request, user_id):
    """View for editing an existing user"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        # Extract common form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        mobile_number = request.POST.get('mobile_number')
        is_active = request.POST.get('is_active') == 'on'
        
        # User type specific data
        if user.user_type == CustomUser.UserType.STAFF:
            staff_role = request.POST.get('staff_role')
            user.staff_role = staff_role
        else:  # RADIO
            radio_station_id = request.POST.get('radio_station')
            is_primary_contact = request.POST.get('is_primary_contact') == 'on'
            
            # Get the radio station
            try:
                station = RadioStation.objects.get(id=radio_station_id)
                user.radio_station = station
                
                # Handle primary contact change
                if is_primary_contact != user.is_primary_contact:
                    if is_primary_contact:
                        # Reset any existing primary contacts
                        station.users.filter(is_primary_contact=True).update(is_primary_contact=False)
                    user.is_primary_contact = is_primary_contact
                
            except RadioStation.DoesNotExist:
                messages.error(request, 'Selected radio station does not exist.')
                return redirect('edit_user', user_id=user.id)
        
        # Update the user
        try:
            user.first_name = first_name
            user.last_name = last_name
            user.mobile_number = mobile_number
            user.is_active = is_active
            user.save()
            
            messages.success(request, f'User "{user.email}" has been updated.')
            return redirect('user_list')
        
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    # GET request - show the form with current data
    context = {'user': user}
    
    if user.user_type == CustomUser.UserType.STAFF:
        context['staff_roles'] = CustomUser.StaffRole.choices
        return render(request, 'accounts/users/edit_staff.html', context)
    else:  # RADIO
        context['stations'] = RadioStation.objects.all().order_by('name')
        return render(request, 'accounts/users/edit_radio.html', context)

@login_required
@admin_required
def delete_user(request, user_id):
    """View for deleting a user"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        email = user.email
        user.delete()
        messages.success(request, f'User "{email}" has been deleted.')
        return redirect('user_list')
    
    return render(request, 'accounts/users/delete_confirm.html', {
        'user': user,
    })

@login_required
@admin_required
def reset_password(request, user_id):
    """View for resetting a user's password"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        password = request.POST.get('password')
        
        if not password:
            messages.error(request, 'Password is required.')
            return render(request, 'accounts/users/reset_password.html', {
                'user': user,
            })
        
        try:
            user.set_password(password)
            user.save()
            messages.success(request, f'Password for "{user.email}" has been reset.')
            return redirect('user_list')
        
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    return render(request, 'accounts/users/reset_password.html', {
        'user': user,
    })