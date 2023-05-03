from osc4py3 import oscbuildparse
from osc4py3.as_eventloop import osc_send, osc_udp_client
from abc import ABC
from typing import Dict, Any
from .pattern import *
from time import time


class BaseStream(ABC):
    """
    A class for playing control pattern events

    It should be subscribed to a LinkClock instance.

    Parameters
    ----------
    name: Optional[str]
        Name of the stream instance

    """

    def __init__(self, name: str = None):
        self.name = name
        self.pattern = None

    def notify_tick(
        self,
        clock,
        cycle: tuple,
        cycles_per_second: float,
        beats_per_cycle: int,
        now: int | float,
    ):
        """Called by a Clock every time it ticks, when subscribed to it"""
        if not self.pattern:
            return

        cycle_from, cycle_to = cycle
        es = self.pattern.onsets_only().query(TimeSpan(cycle_from, cycle_to))
        print(cycle_from, cycle_to, es)

        for e in es:
            cycle_on = e.whole.begin
            cycle_off = e.whole.end

            # Rewrite with the timeAtBeat method
            link_on = clock.timeAtBeat(cycle_on * beats_per_cycle, 0)
            link_off = clock.timeAtBeat(cycle_off * beats_per_cycle, 0)
            delta_secs = (link_off - link_on)

            link_secs = clock.shifted_time + clock._tidal_nudge
            nudge = e.value.get("nudge", 0)
            ts = (link_on) + self.latency + nudge

            self.notify_event(
                e.value,
                timestamp=ts,
                cps=float(cycles_per_second),
                cycle=float(cycle_on),
                delta=float(delta_secs),
            )

    def notify_event(
        self,
        event: Dict[str, Any],
        timestamp: float,
        cps: float,
        cycle: float,
        delta: float,
    ):
        """Called by `notify_tick` with the event and timestamp that should be played"""
        raise NotImplementedError

    def __repr__(self):
        pattern_repr = " \n" + repr(self.pattern) if self.pattern else ""
        return f"<{self.__class__.__name__} {repr(self.name)}{pattern_repr}>"


class SuperDirtStream(BaseStream):
    """
    This Stream class sends control pattern messages to SuperDirt via OSC

    Parameters
    ----------
    port: int
        The port where SuperDirt is listening
    latency: float
        SuperDirt latency

    """

    def __init__(self, osc_client, port=57120, latency=0.0, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.latency = latency
        self.name = "vortex"
        self._osc_client = osc_client

    @property
    def port(self):
        """SuperDirt listening port"""
        return self._port

    def notify_event(
        self,
        event: Dict[str, Any],
        timestamp: float,
        cps: float,
        cycle: float,
        delta: float,
    ):
        msg = []
        for key, val in event.items():
            if isinstance(val, Fraction):
                val = float(val)
            msg.append(key)
            msg.append(val)
        msg.extend(["cps", cps, "cycle", cycle, "delta", delta])

        # TODO: make a bundle using osc4py3
        self._osc_client._send_timed_message(address="/dirt/play", message=msg)
