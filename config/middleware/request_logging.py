import logging
import time
import uuid

logger = logging.getLogger("app")

class RequestLoggingMiddleware:
    """
    Logs every HTTP request & response
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())
        request.request_id = request_id

        start_time = time.time()
        response = self.get_response(request)
        duration = round((time.time() - start_time) * 1000, 2)

        user_id = (
            request.user.id
            if hasattr(request, "user") and request.user.is_authenticated
            else None
        )

        logger.info(
            "HTTP request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration,
                "user_id": user_id,
                "ip": self.get_client_ip(request),
            },
        )

        response["X-Request-ID"] = request_id
        return response

    @staticmethod
    def get_client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0]
        return request.META.get("REMOTE_ADDR")
