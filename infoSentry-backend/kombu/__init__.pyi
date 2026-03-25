class Exchange:
    def __init__(self, name: str, type: str = ...) -> None: ...

class Queue:
    def __init__(
        self,
        name: str,
        exchange: Exchange | None = ...,
        routing_key: str | None = ...,
    ) -> None: ...
