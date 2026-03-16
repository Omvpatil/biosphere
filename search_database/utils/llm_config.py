from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


LLM_RETRY = {
    "wait": wait_exponential(
        multiplier=1,
        min=getattr(settings, "LLM_RETRY_MIN_WAIT", 1),
        max=getattr(settings, "LLM_RETRY_MAX_WAIT", 6),
    ),
    "stop": stop_after_attempt(getattr(settings, "LLM_RETRY_ATTEMPTS", 2)),
    "retry": retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
}
EMBEDDING_RETRY = {
    "wait": wait_exponential(
        multiplier=1,
        min=getattr(settings, "EMBEDDING_RETRY_MIN_WAIT", 2),
        max=getattr(settings, "EMBEDDING_RETRY_MAX_WAIT", 8),
    ),
    "stop": stop_after_attempt(getattr(settings, "EMBEDDING_RETRY_ATTEMPTS", 3)),
    "retry": retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
}

GLINER_RETRY = {
    "wait": wait_exponential(
        multiplier=1,
        min=getattr(settings, "LLM_RETRY_MIN_WAIT", 1),
        max=getattr(settings, "LLM_RETRY_MAX_WAIT", 6),
    ),
    "stop": stop_after_attempt(getattr(settings, "LLM_RETRY_ATTEMPTS", 2)),
    "retry": retry_if_exception_type(),
}
