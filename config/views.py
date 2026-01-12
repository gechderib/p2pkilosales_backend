from rest_framework import viewsets
from .utils import standard_response

class StandardResponseViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that provides standardized response format
    """
    def _standardize_response(self, response):
        """
        Helper method to standardize a response object
        """
        if hasattr(response, 'data') and isinstance(response.data, dict):
            if all(k in response.data for k in ["status", "data", "status_code", "error"]):
                return response

        return standard_response(
            data=response.data if hasattr(response, 'data') else {},
            status_code=response.status_code
        )

    def finalize_response(self, request, response, *args, **kwargs):
        # Check if response is already standardized to avoid double wrapping
        if hasattr(response, 'data') and isinstance(response.data, dict):
            if all(k in response.data for k in ["status", "data", "status_code", "error"]):
                return super().finalize_response(request, response, *args, **kwargs)

        if hasattr(response, 'data'):
            response = standard_response(
                data=response.data,
                status_code=response.status_code
            )
        return super().finalize_response(request, response, *args, **kwargs)

class StandardAPIView(viewsets.views.APIView):
    """
    Base APIView that provides standardized response format
    """
    def _standardize_response(self, response):
        """
        Helper method to standardize a response object
        """
        if hasattr(response, 'data') and isinstance(response.data, dict):
            if all(k in response.data for k in ["status", "data", "status_code", "error"]):
                return response

        return standard_response(
            data=response.data if hasattr(response, 'data') else {},
            status_code=response.status_code
        )

    def finalize_response(self, request, response, *args, **kwargs):
        if hasattr(response, 'data'):
            response = standard_response(
                data=response.data,
                status_code=response.status_code
            )
        return super().finalize_response(request, response, *args, **kwargs)