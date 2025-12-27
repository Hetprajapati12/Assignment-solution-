"""
Tests for Temperature API endpoints.
"""

import io
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestHealthCheckEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_check(self, api_client):
        """Test health check returns 200."""
        response = api_client.get('/api/health/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'healthy'


@pytest.mark.django_db
class TestAuthenticationEndpoints:
    """Tests for authentication endpoints."""
    
    def test_register_user(self, api_client):
        """Test user registration."""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        
        response = api_client.post('/api/auth/register/', data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['username'] == 'newuser'
    
    def test_register_password_mismatch(self, api_client):
        """Test registration fails with mismatched passwords."""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'DifferentPass123!'
        }
        
        response = api_client.post('/api/auth/register/', data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_obtain_token(self, api_client, user):
        """Test obtaining JWT token."""
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = api_client.post('/api/auth/token/', data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
    
    def test_refresh_token(self, api_client, user):
        """Test refreshing JWT token."""
        # First get a token
        token_response = api_client.post('/api/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        refresh_token = token_response.data['refresh']
        
        # Then refresh it
        response = api_client.post('/api/auth/token/refresh/', {
            'refresh': refresh_token
        })
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data


@pytest.mark.django_db
class TestCityEndpoints:
    """Tests for city-related endpoints."""
    
    def test_list_cities_unauthorized(self, api_client):
        """Test that listing cities requires authentication."""
        response = api_client.get('/api/cities/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_list_cities(self, authenticated_client, cities):
        """Test listing cities."""
        response = authenticated_client.get('/api/cities/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 5
    
    def test_get_city_detail(self, authenticated_client, city):
        """Test getting city detail."""
        response = authenticated_client.get(f'/api/cities/{city.city_id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['city_id'] == city.city_id
    
    def test_get_city_not_found(self, authenticated_client):
        """Test getting non-existent city."""
        response = authenticated_client.get('/api/cities/NONEXISTENT/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestTemperatureStatisticsEndpoint:
    """Tests for temperature statistics endpoint."""
    
    def test_get_statistics_unauthorized(self, api_client, city):
        """Test that statistics require authentication."""
        response = api_client.get(f'/api/cities/{city.city_id}/statistics/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_statistics(self, authenticated_client, city_with_cache):
        """Test getting temperature statistics."""
        response = authenticated_client.get(
            f'/api/cities/{city_with_cache.city_id}/statistics/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert 'mean_temperature' in response.data
        assert 'max_temperature' in response.data
        assert 'min_temperature' in response.data
        assert 'reading_count' in response.data
    
    def test_get_statistics_not_found(self, authenticated_client):
        """Test statistics for non-existent city."""
        response = authenticated_client.get('/api/cities/NONEXISTENT/statistics/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestFileUploadEndpoint:
    """Tests for file upload endpoint."""
    
    def test_upload_file(self, authenticated_client, sample_csv_content):
        """Test uploading a CSV file."""
        csv_file = io.BytesIO(sample_csv_content.encode('utf-8'))
        csv_file.name = 'test_data.csv'
        
        response = authenticated_client.post(
            '/api/upload/',
            {'file': csv_file},
            format='multipart'
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert 'upload_id' in response.data
        assert 'task_id' in response.data
    
    def test_upload_invalid_file_type(self, authenticated_client):
        """Test uploading non-CSV file."""
        text_file = io.BytesIO(b'This is not a CSV')
        text_file.name = 'test.txt'
        
        response = authenticated_client.post(
            '/api/upload/',
            {'file': text_file},
            format='multipart'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_upload_no_file(self, authenticated_client):
        """Test upload without file."""
        response = authenticated_client.post('/api/upload/', {}, format='multipart')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTemperatureReadingsEndpoint:
    """Tests for temperature readings endpoint."""
    
    def test_get_readings(self, authenticated_client, city, temperature_readings):
        """Test getting temperature readings for a city."""
        response = authenticated_client.get(f'/api/cities/{city.city_id}/readings/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert response.data['total_count'] == 100
    
    def test_get_readings_with_pagination(self, authenticated_client, city, temperature_readings):
        """Test readings pagination."""
        response = authenticated_client.get(
            f'/api/cities/{city.city_id}/readings/',
            {'limit': 10, 'offset': 0}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 10
        assert response.data['limit'] == 10
        assert response.data['offset'] == 0
    
    def test_get_readings_not_found(self, authenticated_client):
        """Test readings for non-existent city."""
        response = authenticated_client.get('/api/cities/NONEXISTENT/readings/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
