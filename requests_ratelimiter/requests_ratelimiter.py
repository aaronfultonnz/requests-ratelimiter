from inspect import signature
from logging import getLogger
from time import time
from typing import TYPE_CHECKING, Callable, Dict, Iterable, Type, Union
from urllib.parse import urlparse
from uuid import uuid4

from pyrate_limiter import Duration, Limiter, RequestRate
from pyrate_limiter.bucket import AbstractBucket, MemoryQueueBucket
from requests import PreparedRequest, Response, Session
from requests.adapters import HTTPAdapter

if TYPE_CHECKING:
    MIXIN_BASE = Session
else:
    MIXIN_BASE = object
logger = getLogger(__name__)


class LimiterMixin(MIXIN_BASE):
    """Mixin class that adds rate-limiting behavior to requests.

    The following parameters also apply to :py:class:`.LimiterSession` and
    :py:class:`.LimiterAdapter`.

    .. note::
        The ``per_*`` params are aliases for the most common rate limit
        intervals; for more complex rate limits, you can provide a
        :py:class:`~pyrate_limiter.limiter.Limiter` object instead.

    Args:
        per_second: Max requests per second
        per_minute: Max requests per minute
        per_hour: Max requests per hour
        per_day: Max requests per day
        per_month: Max requests per month
        burst: Max number of consecutive requests allowed before applying per-second rate-limiting
        bucket_class: Bucket backend class; may be one of :py:class:`.MemoryQueueBucket` (default),
            :py:class:`.SQLiteBucket`, or :py:class:`.RedisBucket`
        bucket_kwargs: Bucket backend keyword arguments
        limiter: An existing Limiter object to use instead of the above params
        max_delay: The maximum allowed delay time (in seconds); anything over this will abort the
            request and raise a :py:exc:`.BucketFullException`
        per_host: Track request rate limits separately for each host
        limit_statuses: Alternative HTTP status codes that indicate a rate limit was exceeded
    """

    def __init__(
        self,
        per_second: float = 0,
        per_minute: float = 0,
        per_hour: float = 0,
        per_day: float = 0,
        per_month: float = 0,
        burst: float = 1,
        bucket_class: Type[AbstractBucket] = MemoryQueueBucket,
        bucket_kwargs: Dict = None,
        time_function: Callable[..., float] = None,
        limiter: Limiter = None,
        max_delay: Union[int, float] = None,
        per_host: bool = True,
        limit_statuses: Iterable[int] = (429,),
        **kwargs,
    ):
        # Translate request rate values into RequestRate objects
        rates = [
            RequestRate(limit, interval)
            for interval, limit in {
                Duration.SECOND * burst: per_second * burst,
                Duration.MINUTE: per_minute,
                Duration.HOUR: per_hour,
                Duration.DAY: per_day,
                Duration.MONTH: per_month,
            }.items()
            if limit
        ]

        # If using a persistent backend, we don't want to use monotonic time (the default)
        if bucket_class != MemoryQueueBucket and not time_function:
            time_function = time

        self.limiter = limiter or Limiter(
            *rates,
            bucket_class=bucket_class,
            bucket_kwargs=bucket_kwargs,
            time_function=time_function,
        )
        self.limit_statuses = limit_statuses
        self.max_delay = max_delay
        self.per_host = per_host
        self._default_bucket = str(uuid4())

        # If the superclass is an adapter or custom Session, pass along any valid keyword arguments
        session_kwargs = get_valid_kwargs(super().__init__, kwargs)
        super().__init__(**session_kwargs)  # type: ignore  # Base Session doesn't take any kwargs

    # Conveniently, both Session.send() and HTTPAdapter.send() have a mostly consistent signature
    def send(self, request: PreparedRequest, **kwargs) -> Response:
        """Send a request with rate-limiting.

        Raises:
            :py:exc:`.BucketFullException` if this request would result in a delay longer than ``max_delay``
        """
        with self.limiter.ratelimit(
            self._bucket_name(request),
            delay=True,
            max_delay=self.max_delay,
        ):
            response = super().send(request, **kwargs)
            if response.status_code in self.limit_statuses:
                self._fill_bucket(request)
            return response

    def _bucket_name(self, request):
        """Get a bucket name for the given request"""
        return urlparse(request.url).netloc if self.per_host else self._default_bucket

    def _fill_bucket(self, request: PreparedRequest):
        """Partially fill the bucket for the given request, requiring an extra delay until the next
        request. This is essentially an attempt to catch up to the actual (server-side) limit if
        we've gotten out of sync.

        If the server tracks multiple limits, there's no way to know which specific limit was
        exceeded, so the smallest rate will be used.

        For example, if the server allows 60 requests per minute, and we've tracked only 40 requests
        but received a 429 response, 20 additional "filler" requests will be added to the bucket to
        attempt to catch up to the server-side limit.

        If the server also has an hourly limit, we don't have enough information to know if we've
        exceeded that limit or how long to delay, so we'll keep delaying in 1-minute intervals.
        """
        logger.info(f'Rate limit exceeded for {request.url}; filling limiter bucket')
        bucket = self.limiter.bucket_group[self._bucket_name(request)]

        # Determine how many requests we've made within the smallest defined time interval
        now = self.limiter.time_function()
        rate = self.limiter._rates[0]
        item_count, _ = bucket.inspect_expired_items(now - rate.interval)

        # Add "filler" requests to reach the limit for that interval
        for _ in range(rate.limit - item_count):
            bucket.put(now)


class LimiterSession(LimiterMixin, Session):
    """`Session <https://requests.readthedocs.io/en/latest/user/advanced/#session-objects>`_
    that adds rate-limiting behavior to requests.
    """


class LimiterAdapter(LimiterMixin, HTTPAdapter):  # type: ignore  # send signature accepts **kwargs
    """`Transport adapter
    <https://requests.readthedocs.io/en/latest/user/advanced/#transport-adapters>`_
    that adds rate-limiting behavior to requests.
    """


def get_valid_kwargs(func: Callable, kwargs: Dict) -> Dict:
    """Get the subset of non-None ``kwargs`` that are valid params for ``func``"""
    sig_params = list(signature(func).parameters)
    return {k: v for k, v in kwargs.items() if k in sig_params and v is not None}
