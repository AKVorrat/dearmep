import ipaddress
import logging
from time import time
from typing import Dict, Literal, Optional, Tuple, Union

from fastapi import Depends, HTTPException, Request, routing, status
import limits
from prometheus_client import Counter

from .config import Config, IPRateLimits


NETSIZES: Dict[str, Union[None, Tuple[int, int]]] = {
    "ip": None,
    "small_block": (24, 64),
    "large_block": (16, 48),
}


_logger = logging.getLogger(__name__)


# The storage is implemented in `limits` with a weak reference, therefore we
# need to keep a reference here.
limits_storage = limits.storage.MemoryStorage()
moving_window = limits.strategies.MovingWindowRateLimiter(limits_storage)


http_ratelimit_total = Counter(
    "http_ratelimit_total",
    "Number of times a rate limit was passed or hit, by endpoint/method.",
    ("method", "path", "result"),
)


def client_addr(request: Request) -> str:
    """Retrieve the client's IP address.

    This can be used as a dependency, mainly to enable swapping it out while
    running the test suite.
    """
    # Always return a string. If we don't know the client's host, return a
    # string nevertheless.
    return request.client.host if request.client else ""


def ip_network(
    addr: Union[ipaddress.IPv4Address, ipaddress.IPv6Address],
    *,
    v4len: int = 32,
    v6len: int = 128,
) -> str:
    net: Union[ipaddress.IPv4Network, ipaddress.IPv6Network] = (
        ipaddress.IPv4Network((addr, v4len), strict=False)
        if isinstance(addr, ipaddress.IPv4Address)
        else ipaddress.IPv6Network((addr, v6len), strict=False))
    return net.with_prefixlen


class Limit:
    """Dependency for rate limiting calls of an endpoint."""

    @staticmethod
    def reset_all_limits():
        limits_storage.reset()

    def __init__(self, limit_name: Literal["simple", "computational", "sms"]):
        self.limit_name = limit_name
        self.limits: Optional[Dict[str, limits.RateLimitItem]] = None

    def __call__(self, request: Request, addr_str=Depends(client_addr)):
        if self.limits is None:
            # First call, we need to get the values from the Config.
            rate_limits: IPRateLimits = getattr(
                Config.get().api.rate_limits, self.limit_name)
            self.limits = {
                name: limits.parse(getattr(rate_limits, f"{name}_limit"))
                for name in NETSIZES
            }
        route: routing.APIRoute = request.scope["route"]
        prom_labels = (request.method, route.path)

        if addr_str == "":
            _logger.warning("client address unknown, rate limiting skipped")
            return

        try:
            addr = ipaddress.ip_address(addr_str)
        except ValueError:
            _logger.warning(
                "client address seems to be a hostname, not an IP address, "
                "rate limiting skipped")
            return

        for size_name, netsizes in NETSIZES.items():
            limit = self.limits[size_name]
            identifiers = (  # this is a tuple with one item
                ip_network(addr, v4len=netsizes[0], v6len=netsizes[1])
                if netsizes else ip_network(addr),)
            reset_at = moving_window.get_window_stats(limit, *identifiers)[0]

            if moving_window.hit(limit, *identifiers):
                # Within the limit. Do nothing, except counting it.
                http_ratelimit_total.labels(*prom_labels, "pass").inc()
                continue

            # Limit exceeded.
            http_ratelimit_total.labels(*prom_labels, "hit").inc()
            reset_in = max(1, round(reset_at - time()))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"rate limit exceeded, try again in {reset_in} "
                f"second{'' if reset_in == 1 else 's'}",
                headers={"Retry-After": str(reset_in)},
            )
