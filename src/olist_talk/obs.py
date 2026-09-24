import logfire

_done = False


def setup() -> None:
    """Configure Logfire once. No-ops safely when no token is present."""
    global _done
    if _done:
        return
    logfire.configure(
        service_name="olist-talk",
        send_to_logfire="if-token-present",
        console=False,
    )
    logfire.instrument_pydantic_ai()
    _done = True
