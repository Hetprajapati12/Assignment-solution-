"""
Serializers for Temperature API.

Provides serialization/deserialization for:
- Temperature readings
- City statistics
- File upload status
- User registration
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import City, TemperatureReading, CityTemperatureCache, FileUpload


class TemperatureReadingSerializer(serializers.ModelSerializer):
    """Serializer for individual temperature readings."""
    
    city_id = serializers.CharField(source='city.city_id', read_only=True)

    class Meta:
        model = TemperatureReading
        fields = ['id', 'city_id', 'temperature', 'timestamp', 'created_at']
        read_only_fields = ['id', 'created_at']


class CitySerializer(serializers.ModelSerializer):
    """Serializer for city information."""
    
    reading_count = serializers.SerializerMethodField()

    class Meta:
        model = City
        fields = ['city_id', 'name', 'reading_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_reading_count(self, obj):
        """Get the total number of readings for this city."""
        return obj.temperature_readings.count()


class CityTemperatureStatisticsSerializer(serializers.Serializer):
    """
    Serializer for city temperature statistics.
    
    Returns mean, max, min temperatures for a city.
    """
    
    city_id = serializers.CharField()
    mean_temperature = serializers.FloatField(allow_null=True)
    max_temperature = serializers.FloatField(allow_null=True)
    min_temperature = serializers.FloatField(allow_null=True)
    reading_count = serializers.IntegerField()
    last_updated = serializers.DateTimeField(required=False, allow_null=True)
    cached = serializers.BooleanField(default=False)


class CityTemperatureCacheSerializer(serializers.ModelSerializer):
    """Serializer for cached city temperature statistics."""
    
    city_id = serializers.CharField(source='city.city_id', read_only=True)

    class Meta:
        model = CityTemperatureCache
        fields = [
            'city_id', 'mean_temperature', 'max_temperature',
            'min_temperature', 'reading_count', 'last_updated', 'is_stale'
        ]
        read_only_fields = fields


class FileUploadSerializer(serializers.ModelSerializer):
    """Serializer for file upload status and details."""
    
    progress_percentage = serializers.FloatField(read_only=True)
    uploaded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = FileUpload
        fields = [
            'id', 'filename', 'file_size', 'status', 'total_rows',
            'processed_rows', 'progress_percentage', 'error_count',
            'error_messages', 'retry_count', 'created_at', 'updated_at',
            'completed_at', 'uploaded_by'
        ]
        read_only_fields = fields


class FileUploadRequestSerializer(serializers.Serializer):
    """Serializer for file upload requests."""
    
    file = serializers.FileField(
        help_text="CSV file containing temperature readings (city_id,temp,timestamp)"
    )

    def validate_file(self, value):
        """Validate the uploaded file."""
        # Check file extension
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("Only CSV files are accepted.")
        
        # Check file size (max 500 MB)
        max_size = 500 * 1024 * 1024  # 500 MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size exceeds maximum allowed size of 500 MB."
            )
        
        return value


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
        }

    def validate(self, attrs):
        """Validate that passwords match."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password_confirm": "Password fields didn't match."
            })
        return attrs

    def validate_email(self, value):
        """Validate email uniqueness."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        """Create a new user."""
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class BulkTemperatureUploadSerializer(serializers.Serializer):
    """Serializer for bulk temperature reading upload via JSON."""
    
    readings = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=10000,
        help_text="List of temperature readings"
    )

    def validate_readings(self, value):
        """Validate each reading in the list."""
        validated_readings = []
        errors = []
        
        for i, reading in enumerate(value):
            if 'city_id' not in reading:
                errors.append(f"Row {i}: Missing 'city_id'")
                continue
            if 'temp' not in reading and 'temperature' not in reading:
                errors.append(f"Row {i}: Missing 'temp' or 'temperature'")
                continue
            if 'timestamp' not in reading:
                errors.append(f"Row {i}: Missing 'timestamp'")
                continue
            
            try:
                temp = float(reading.get('temp') or reading.get('temperature'))
                if temp < -100 or temp > 100:
                    errors.append(f"Row {i}: Temperature {temp} out of valid range")
                    continue
            except (ValueError, TypeError):
                errors.append(f"Row {i}: Invalid temperature value")
                continue
            
            validated_readings.append({
                'city_id': str(reading['city_id']),
                'temperature': temp,
                'timestamp': reading['timestamp']
            })
        
        if errors:
            raise serializers.ValidationError(errors[:10])  # Return first 10 errors
        
        return validated_readings
