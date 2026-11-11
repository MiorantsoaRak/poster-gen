"""One claimed job: preflight, retry-free dispatch, bounded 429 retry and local result recovery."""
import asyncio
from dataclasses import dataclass
import logging

from sqlalchemy.exc import SQLAlchemyError

from affiche.visuals.gateway import ProviderError
from . import jobs
from .planner import PlannerError
from .store import Refused

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Outcome:
    result: dict
    usage: dict | None = None
    cost_micros: int | None = None
    request_id: str | None = None


def _call(engine, id):
    with engine.connect() as conn:
        row = jobs.current_call(conn, id)
        return dict(row) if row else None


async def finalise_saved(engine, settings, id, finalise) -> bool:
    for attempt in range(2):
        try:
            await asyncio.to_thread(jobs.finish_spool, engine, settings.data_dir, id, finalise)
            return True
        except (OSError, SQLAlchemyError) as error:
            log.warning("poster %s local finalisation unavailable: %s", id, type(error).__name__)
            if attempt == 0:
                await asyncio.sleep(.5)
    # Keep the running job and spool: the worker sweep/startup retries only local finalisation.
    return False


async def run_job(engine, settings, job, *, prepare, send, finalise) -> bool:
    """prepare(job, call) is local; send(prepared) returns Outcome; finalise runs in the result transaction."""
    id = job["id"]
    if await asyncio.to_thread(jobs.spool_path(settings.data_dir, id).exists):
        return await finalise_saved(engine, settings, id, finalise)
    call = await asyncio.to_thread(_call, engine, id)
    try:
        prepared = await asyncio.to_thread(prepare, job, call)
    except Exception as error:
        log.warning("poster %s preflight failed: %s", id, type(error).__name__)
        await asyncio.to_thread(jobs.fail, engine, id, "preflight_failed", unsent=True)
        return False
    while True:
        if call:
            call = await asyncio.to_thread(jobs.dispatch, engine, id)
        try:
            outcome = await send(prepared)
        except (ProviderError, PlannerError) as error:
            code = error.kind if isinstance(error, ProviderError) else error.code
            rate_limit = code in {"rate_limited", "planner_rate_limited"}
            if rate_limit and call:
                try:
                    retry = await asyncio.to_thread(jobs.reserve_rate_limit_retry, engine, settings, id)
                except Refused as refused:
                    if refused.code != "budget_exhausted":
                        raise
                    retry = False
                if retry:
                    await asyncio.sleep(2)
                    continue
            ambiguous = (error.ambiguous if isinstance(error, PlannerError) else code in {"timeout", "provider_error"})
            await asyncio.to_thread(jobs.fail, engine, id, code, ambiguous=ambiguous,
                                    usage=getattr(error, "usage", None),
                                    cost_micros=0 if rate_limit else getattr(error, "cost_micros", None))
            return False
        except Refused as error:
            await asyncio.to_thread(jobs.fail, engine, id, error.code, unsent=call is None)
            return False
        except Exception as error:
            log.warning("poster %s execution failed: %s", id, type(error).__name__)
            await asyncio.to_thread(jobs.fail, engine, id, "execution_failed", ambiguous=call is not None)
            return False
        break
    if not isinstance(outcome, Outcome):
        await asyncio.to_thread(jobs.fail, engine, id, "invalid_result")
        return False
    for attempt in range(2):
        try:
            await asyncio.to_thread(jobs.spool, settings.data_dir, job, outcome.result, usage=outcome.usage,
                                    cost_micros=outcome.cost_micros, request_id=outcome.request_id)
            break
        except OSError as error:
            log.warning("poster %s result spool unavailable: %s", id, type(error).__name__)
            if attempt == 0:
                await asyncio.sleep(.5)
            else:
                await asyncio.to_thread(jobs.fail, engine, id, "reconciliation_required", ambiguous=call is not None,
                                        usage=outcome.usage, cost_micros=outcome.cost_micros)
                return False
        except (ValueError, TypeError):
            await asyncio.to_thread(jobs.fail, engine, id, "invalid_result")
            return False
    return await finalise_saved(engine, settings, id, finalise)
