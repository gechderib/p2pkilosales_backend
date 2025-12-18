import logging
import time
import uuid

logger = logging.getLogger("app")

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        status = response.status_code

        if status >= 500:
            log_level = logger.error
        elif status >= 400:
            log_level = logger.warning
        else:
            log_level = logger.info

        log_level(
            "HTTP request completed",
            extra={
                "request_id": getattr(request, "request_id", None),
                "method": request.method,
                "path": request.path,
                "status_code": status,
                "duration_ms": duration_ms,
                "user_id": (
                    getattr(request, "user", None).id
                    if hasattr(request, "user") and request.user.is_authenticated
                    else None
                ),
                "ip": request.META.get("REMOTE_ADDR"),
            },
        )

        return response

    @staticmethod
    def get_client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0]
        return request.META.get("REMOTE_ADDR")
