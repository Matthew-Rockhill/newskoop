# accounts/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import RadioStation

User = get_user_model()

class RadioStationSerializer(serializers.ModelSerializer):
    """Serializer for radio stations"""
    class Meta:
        model = RadioStation
        fields = [
            'id', 'name', 'code', 'description', 'address', 
            'contact_number', 'contact_email', 'website', 'is_active',
            'access_general', 'access_christian', 'access_muslim',
            'access_english', 'access_afrikaans', 'access_xhosa',
            'access_news_stories', 'access_news_bulletins', 
            'access_sport', 'access_finance', 'access_specialty',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    """Serializer for displaying user details"""
    radio_station_name = serializers.CharField(source='radio_station.name', read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'mobile_number',
            'is_active', 'is_staff', 'date_joined', 'user_type',
            'staff_role', 'radio_station', 'radio_station_name', 'is_primary_contact'
        ]
        read_only_fields = ['id', 'date_joined', 'is_active', 'is_staff']
        

class StaffUserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new staff users"""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'first_name', 'last_name', 
            'mobile_number', 'staff_role', 'is_active'
        ]
    
    def validate(self, data):
        # Add fixed field values for staff users
        data['user_type'] = User.UserType.STAFF
        
        # Validate staff_role is provided
        if not data.get('staff_role'):
            raise serializers.ValidationError({"staff_role": "This field is required for staff users."})
        
        return data
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class RadioUserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new radio station users"""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'first_name', 'last_name', 
            'mobile_number', 'radio_station', 'is_primary_contact', 'is_active'
        ]
    
    def validate(self, data):
        # Add fixed field values for radio users
        data['user_type'] = User.UserType.RADIO
        
        # Validate radio_station is provided
        if not data.get('radio_station'):
            raise serializers.ValidationError({"radio_station": "This field is required for radio station users."})
        
        # Validate is_primary_contact when creating a new primary contact
        if data.get('is_primary_contact'):
            # Check if there's already a primary contact for this station
            station = data['radio_station']
            existing_primary = User.objects.filter(
                radio_station=station, 
                is_primary_contact=True
            ).exists()
            
            if existing_primary:
                raise serializers.ValidationError(
                    {"is_primary_contact": "This station already has a primary contact."}
                )
        
        return data
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class RadioUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating radio station users"""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'mobile_number', 
            'radio_station', 'is_primary_contact', 'is_active'
        ]
    
    def validate(self, data):
        # Validate is_primary_contact when updating to be a primary contact
        if data.get('is_primary_contact'):
            # Get the radio station (either from the data or the instance)
            station = data.get('radio_station') or self.instance.radio_station
            
            # Check if there's already a primary contact for this station (excluding this user)
            existing_primary = User.objects.filter(
                radio_station=station, 
                is_primary_contact=True
            ).exclude(id=self.instance.id).exists()
            
            if existing_primary:
                raise serializers.ValidationError(
                    {"is_primary_contact": "This station already has a primary contact."}
                )
        
        return data


class StaffUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating staff users"""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'mobile_number', 
            'staff_role', 'is_active'
        ]