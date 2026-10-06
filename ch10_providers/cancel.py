"""Cancellation end to end: the tab closes, every layer below stops."""
import asyncio

TOKENS = 430            # a long answer: 43 seconds at ten tokens a second


async def provider_stream(log, clock):
    """Stand-in for a provider generating a token every 0.1 s."""
    try:
        for _ in range(TOKENS):
            await clock.sleep(0.1)
            log["tokens"] += 1
    finally:
        log["closed_at"] = clock.now()      # the adapter closes up


async def queued_retry(log, clock):
    await clock.sleep(5)                    # a retry waiting its turn
    log["retry_ran"] = True


async def handle_leaky(log, clock):
    """The bug: the stream is started as a task nobody owns."""
    log["ghost"] = asyncio.create_task(provider_stream(log, clock))
    await clock.sleep(60)                   # waiting for the answer


async def handle_chat(log, clock):
    """A handler owns its children: they stop when it stops."""
    stream = asyncio.create_task(provider_stream(log, clock))
    retry = asyncio.create_task(queued_retry(log, clock))
    try:
        await stream
        log["tool_started"] = True          # only after a whole answer
    finally:
        for task in (stream, retry):
            task.cancel()
        await asyncio.gather(stream, retry, return_exceptions=True)


async def pay_refund(log, clock):
    await clock.sleep(0.5)                  # talking to payments
    log["refund"] = "paid"


async def refund_step(log, clock):
    """A cancel may stop the waiting, never the paying."""
    payment = asyncio.create_task(pay_refund(log, clock))
    try:
        await asyncio.shield(payment)
    except asyncio.CancelledError:
        while not payment.done():           # however many cancels come
            try:
                await asyncio.shield(payment)
            except asyncio.CancelledError:
                pass                        # finish, record, then obey
        raise


async def gateway(handler, log, clock, closes_at, again=None):
    """Notice the closed tab and cancel the request's task."""
    task = asyncio.create_task(handler(log, clock))
    await clock.sleep(closes_at)            # the customer leaves here
    task.cancel()
    log["cancelled_at"] = clock.now()
    log["tokens_at_cancel"] = log["tokens"]
    if again is not None:                   # a second cancel: a deadline
        await clock.sleep(again)
        task.cancel()
    try:
        await task
        log["status"] = "finished"
    except asyncio.CancelledError:
        log["status"] = "cancelled"         # not "failed"
    await clock.sleep(60)                   # watch what happens next
    return log


def fresh_log():
    return {"tokens": 0, "tool_started": False, "retry_ran": False,
            "closed_at": None, "status": None}


def record_outcome(breaker, status):
    """Cancelled is not failed: only real outcomes move the breaker."""
    if status == "cancelled":
        return
    breaker.record(status == "complete")
