from prometheus_client import Counter, Summary

from ...models import UserPhone


class ElksMetrics:
    provider = "46elks"

    call_duration_seconds = Summary(
        name="call_duration_seconds",
        documentation="how long was user connected to MEP in seconds",
        labelnames=("provider", "destination_id"),
    )
    call_cost_euros = Summary(
        name="call_cost_euros",
        documentation="accumulated call costs in Euros",
        labelnames=("provider", "destination_id"),
    )
    call_start_total = Counter(
        name="call_start_total",
        documentation="number of calls started to Destination",
        labelnames=("provider", "destination_number", "our_number"),
    )
    call_end_total = Counter(
        name="call_end_total",
        documentation="number of calls ended with Destination",
        labelnames=("provider", "destination_number", "our_number"),
    )
    call_in_menu_limit_reached_total = Counter(
        name="call_in_menu_limit_reached_total",
        documentation="call reached the limit of time being allowed in menu",
        labelnames=("provider",),
    )
    sms_sent_total = Counter(
        name="sms_sent_total",
        documentation="number of SMS messages sent out",
        labelnames=("provider", "country"),
    )
    sms_parts_sent_total = Counter(
        name="sms_parts_sent_total",
        documentation="number of SMS parts sent out",
        labelnames=("provider", "country"),
    )
    sms_cost_euros = Summary(
        name="sms_cost_euros",
        documentation="accumulated SMS cost in Euros",
        labelnames=("provider", "country"),
    )

    def observe_connect_time(self,
                             destination_id: str,
                             duration: int
                             ):
        """Track the connected calltime of user to MEP in seconds"""
        self.call_duration_seconds.labels(
            provider=self.provider,
            destination_id=destination_id
        ).observe(duration)

    def observe_cost(self,
                     destination_id: str,
                     cost: int
                     ):
        """Track how much the call cost"""
        self.call_cost_euros.labels(
            provider=self.provider,
            destination_id=destination_id
        ).observe(cost / 10_000)

    def inc_start(self,
                  destination_number: str,
                  our_number: str
                  ):
        """Track a started call to MEP"""
        self.call_start_total.labels(
            provider=self.provider,
            destination_number=destination_number,
            our_number=our_number
        ).inc()

    def inc_end(self,
                destination_number: str,
                our_number: str
                ):
        """Track an ended call to MEP"""
        self.call_end_total.labels(
            provider=self.provider,
            destination_number=destination_number,
            our_number=our_number
        ).inc()

    def inc_menu_limit(self):
        """Track a call that reached the limit of time being allowed in menu"""
        self.call_in_menu_limit_reached_total.labels(
            provider=self.provider
        ).inc()

    def observe_sms_cost(
        self,
        *,
        cost: int,
        parts: int,
        recipient: str,
    ):
        country = str(UserPhone(recipient).calling_code)
        self.sms_sent_total \
            .labels(provider=self.provider, country=country) \
            .inc()
        self.sms_parts_sent_total \
            .labels(provider=self.provider, country=country) \
            .inc(parts)
        self.sms_cost_euros \
            .labels(provider=self.provider, country=country) \
            .observe(cost / 10_000)


elks_metrics: ElksMetrics = ElksMetrics()
