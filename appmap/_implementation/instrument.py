from collections import namedtuple
from contextlib import contextmanager
from functools import wraps, WRAPPER_ASSIGNMENTS
import logging
import sys
import time

from . import event
from .event import CallEvent
from .recording import Recorder
from .utils import appmap_tls, split_function_name

logger = logging.getLogger(__name__)


@contextmanager
def recording_disabled():
    tls = appmap_tls()
    tls['instrumentation_disabled'] = True
    try:
        yield
    finally:
        tls['instrumentation_disabled'] = False


def is_instrumentation_disabled():
    return appmap_tls().setdefault('instrumentation_disabled', False)


def track_shallow(fn):
    """
    Check if the function should be skipped because of a shallow rule.
    If not, updates the last rule tracking and return False.

    This works by remembering last matched rule.  This is rather
    simple and the results are not always correct.  For example,
    consider execution flow where code matching another shallow rule
    repeatedly gets called from the code that's already shallow.  It's
    difficult, if at all possible, to generally ensure correctness
    without tracking all execution or analyzing the call stack on each
    call, which is probably too inefficient.

    However, in the most useful case where we're interested in the
    interaction between client code and specific third-party libraries
    while ignoring their internals, it's an effective way of limiting
    appmap size.  If you want anything more complicated and can take
    the performance hit, your best bet is to record without shallow
    and postprocess the appmap to your liking.
    """
    tls = appmap_tls()
    rule = getattr(fn, '_appmap_shallow', None)
    logger.debug('track_shallow(%r) [%r]', fn, rule)
    result = rule and tls.get('last_rule', None) == rule
    tls['last_rule'] = rule
    return result


@contextmanager
def saved_shallow_rule():
    """
    A context manager to save and reset the current shallow tracking
    rule around the call to an instrumented function.
    """
    tls = appmap_tls()
    current_rule = tls.get('last_rule', None)
    try:
        yield
    finally:
        tls['last_rule'] = current_rule


_InstrumentedFn = namedtuple('_InstrumentedFn',
                             'fn, instrumented_fn, make_call_event, params')


def call_instrumented(f, *args, **kwargs):
    if (
        (not Recorder().enabled)
        or is_instrumentation_disabled()
        or track_shallow(f.instrumented_fn)
    ):
        return f.fn(*args, **kwargs)

    with recording_disabled():
        logger.debug('%s args %s kwargs %s', f.fn, args, kwargs)
        call_event = f.make_call_event(
            parameters=CallEvent.set_params(f.params, args, kwargs))
    call_event_id = call_event.id
    Recorder().add_event(call_event)
    start_time = time.time()
    try:
        ret = f.fn(*args, **kwargs)
        elapsed_time = time.time() - start_time

        return_event = event.FuncReturnEvent(return_value=ret,
                                             parent_id=call_event_id,
                                             elapsed=elapsed_time)
        Recorder().add_event(return_event)
        return ret
    except Exception:  # noqa: E722
        elapsed_time = time.time() - start_time
        Recorder().add_event(event.ExceptionEvent(parent_id=call_event_id,
                                                  elapsed=elapsed_time,
                                                  exc_info=sys.exc_info()))
        raise


def instrument(fn, fntype):
    """return an instrumented function"""
    logger.debug('hooking %s', '.'.join(split_function_name(fn)))

    make_call_event = event.CallEvent.make(fn, fntype)
    params = CallEvent.make_params(fn)

    # django depends on being able to find the cache_clear attribute
    # on functions. (You can see this by trying to map
    # https://github.com/chicagopython/chypi.org.) Make sure it gets
    # copied from the original to the wrapped function.
    #
    # Going forward, we should consider how to make this more general.
    @wraps(fn, assigned=WRAPPER_ASSIGNMENTS + tuple(['cache_clear']))
    def instrumented_fn(*args, **kwargs):
        with saved_shallow_rule():
            f = _InstrumentedFn(fn, instrumented_fn, make_call_event, params)
            return call_instrumented(f, *args, **kwargs)

    setattr(instrumented_fn, '_appmap_wrapped', True)
    return instrumented_fn
