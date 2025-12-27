"""
Utility functions for Temperature API.

Provides:
- Custom exception handler for DRF
- Helper functions for data processing
- Validation utilities
"""

import logging
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotAuthenticated,
    AuthenticationFailed,
    PermissionDenied,
    NotFound,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> Optional[Response]:
    """
    Custom exception handler for Django REST Framework.
    
    Provides consistent error response format across all API endpoints.
    
    Args:
        exc: The exception that was raised
        context: Additional context about the request
        
    Returns:
        Response object with formatted error details
    """
    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)
    
    # Get request info for logging
    request = context.get('request')
    view = context.get('view')
    
    if response is not None:
        # Customize the response format
        error_response = {
            'success': False,
            'error': {
                'code': get_error_code(exc),
                'message': get_error_message(exc, response),
                'details': response.data if isinstance(response.data, dict) else {'message': response.data}
            }
        }
        
        response.data = error_response
        
        # Log the error
        log_exception(exc, request, view, response.status_code)
        
        return response
    
    # Handle unexpected exceptions
    if isinstance(exc, DjangoValidationError):
        error_response = {
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Validation failed',
                'details': {'errors': exc.messages if hasattr(exc, 'messages') else [str(exc)]}
            }
        }
        
        log_exception(exc, request, view, 400)
        
        return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle unhandled exceptions
    logger.exception(f"Unhandled exception: {exc}")
    
    error_response = {
        'success': False,
        'error': {
            'code': 'INTERNAL_SERVER_ERROR',
            'message': 'An unexpected error occurred. Please try again later.',
            'details': {}
        }
    }
    
    return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_error_code(exc: Exception) -> str:
    """
    Get a machine-readable error code for an exception.
    
    Args:
        exc: The exception
        
    Returns:
        Error code string
    """
    error_codes = {
        NotAuthenticated: 'AUTHENTICATION_REQUIRED',
        AuthenticationFailed: 'AUTHENTICATION_FAILED',
        PermissionDenied: 'PERMISSION_DENIED',
        NotFound: 'NOT_FOUND',
        Http404: 'NOT_FOUND',
        ValidationError: 'VALIDATION_ERROR',
    }
    
    for exc_class, code in error_codes.items():
        if isinstance(exc, exc_class):
            return code
    
    if isinstance(exc, APIException):
        return exc.default_code.upper() if hasattr(exc, 'default_code') else 'API_ERROR'
    
    return 'UNKNOWN_ERROR'


def get_error_message(exc: Exception, response: Response) -> str:
    """
    Get a human-readable error message for an exception.
    
    Args:
        exc: The exception
        response: The DRF response object
        
    Returns:
        Error message string
    """
    if isinstance(response.data, dict):
        if 'detail' in response.data:
            return str(response.data['detail'])
        if 'message' in response.data:
            return str(response.data['message'])
    
    if hasattr(exc, 'detail'):
        return str(exc.detail)
    
    return str(exc)


def log_exception(
    exc: Exception,
    request: Any,
    view: Any,
    status_code: int
) -> None:
    """
    Log exception details for monitoring and debugging.
    
    Args:
        exc: The exception
        request: The request object
        view: The view that raised the exception
        status_code: HTTP status code
    """
    log_data = {
        'exception_type': type(exc).__name__,
        'exception_message': str(exc),
        'status_code': status_code,
        'path': getattr(request, 'path', 'unknown'),
        'method': getattr(request, 'method', 'unknown'),
        'view': view.__class__.__name__ if view else 'unknown',
    }
    
    if status_code >= 500:
        logger.error(f"Server error: {log_data}", exc_info=exc)
    elif status_code >= 400:
        logger.warning(f"Client error: {log_data}")
    else:
        logger.debug(f"Exception handled: {log_data}")


def validate_csv_row(row: list, row_number: int) -> Dict[str, Any]:
    """
    Validate a CSV row for temperature data.
    
    Args:
        row: List of values from CSV row
        row_number: Row number for error reporting
        
    Returns:
        Dictionary with validated data
        
    Raises:
        ValidationError: If validation fails
    """
    if len(row) < 3:
        raise ValidationError(f"Row {row_number}: Expected 3 columns, got {len(row)}")
    
    city_id = str(row[0]).strip()
    if not city_id:
        raise ValidationError(f"Row {row_number}: Empty city_id")
    
    try:
        temperature = float(row[1])
        if temperature < -100 or temperature > 100:
            raise ValidationError(
                f"Row {row_number}: Temperature {temperature} out of valid range (-100 to 100)"
            )
    except ValueError:
        raise ValidationError(f"Row {row_number}: Invalid temperature value '{row[1]}'")
    
    timestamp = str(row[2]).strip()
    if not timestamp:
        raise ValidationError(f"Row {row_number}: Empty timestamp")
    
    return {
        'city_id': city_id,
        'temperature': temperature,
        'timestamp': timestamp
    }


def calculate_statistics(values: list) -> Dict[str, Optional[float]]:
    """
    Calculate basic statistics for a list of values.
    
    Args:
        values: List of numeric values
        
    Returns:
        Dictionary with mean, max, min values
    """
    if not values:
        return {
            'mean': None,
            'max': None,
            'min': None,
            'count': 0
        }
    
    return {
        'mean': round(sum(values) / len(values), 2),
        'max': round(max(values), 2),
        'min': round(min(values), 2),
        'count': len(values)
    }
