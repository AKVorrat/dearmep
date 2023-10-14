from prometheus_client import Counter, Summary


class ElksMetrics:
    provider = "46elks"

    call_connect_time = Summary(
        name="call_connect_time",
        documentation="how long was user connected to MEP in seconds",
        labelnames=("provider", "destination_id")
    )
    call_cost = Summary(
        name="call_cost",
        documentation="how much was the call in 100 = 1 cent",
        labelnames=("provider", "destination_id")
    )
    call_start_total = Counter(
        name="call_start",
        documentation="call started to MEP",
        labelnames=("provider", "destination_number", "our_number")
    )
    call_end_total = Counter(
        name="call_end",
        documentation="call ended to MEP",
        labelnames=("provider", "destination_number", "our_number")
    )

    def observe_connect_time(self,
                             destination_id: str,
                             duration: int
                             ):
        """Track the connected calltime of user to MEP in seconds"""
        self.call_connect_time.labels(
            provider=self.provider,
            destination_id=destination_id
        ).observe(duration)

    def observe_cost(self,
                     destination_id: str,
                     cost: int
                     ):
        """Track how much the call cost"""
        self.call_cost.labels(
            provider=self.provider,
            destination_id=destination_id
        ).observe(cost)

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


elks_metrics: ElksMetrics = ElksMetrics()
