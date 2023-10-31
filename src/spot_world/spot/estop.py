import logging
from bosdyn.client.estop import EstopClient, EstopEndpoint, EstopKeepAlive, StopLevel

logger = logging.getLogger(__name__)


class EstopError(Exception):
    pass


class EstopStatus:
    NONE = 'NONE'
    ESTOPPED = 'ESTOPPED'
    NOT_ESTOPPED = 'NOT_ESTOPPED'
    ERROR = 'ERROR'


class EstopFacade:

    def __init__(self, spot):
        self._spot = spot
        self._endpoint = None
        self._keepalive = None

    @property
    def client(self):
        return self._spot._robot.ensure_client(EstopClient.default_service_name)

    @property
    def status(self):
        # do we have an estop setup from this console app
        if self._endpoint is None or self._keepalive is None:
            return EstopStatus.NONE
        # is the latest update from the keepalive ok
        if self._keepalive.status_queue.get()[0] != EstopKeepAlive.KeepAliveStatus.OK:
            return EstopStatus.ERROR
        # get the status from the robot
        stop_level = self.client.get_status().stop_level
        if stop_level == StopLevel.ESTOP_LEVEL_NONE:
            return EstopStatus.NOT_ESTOPPED
        elif stop_level in [StopLevel.ESTOP_LEVEL_CUT, StopLevel.ESTOP_LEVEL_SETTLE_THEN_CUT]:
            return EstopStatus.ESTOPPED
        # if we couldn't resolve a status to return consider it an error
        return EstopStatus.ERROR

    def setup(self, timeout_seconds=5):
        if self._endpoint is not None or self._keepalive is not None:
            raise EstopError('estop endpoint is already active')
        self._endpoint = EstopEndpoint(self.client, f"spot-console-estop", timeout_seconds)
        self._endpoint.force_simple_setup()
        self._keepalive = EstopKeepAlive(self._endpoint, max_status_queue_size=1)
        # todo: what if we don't do this during registration? do we start estopped?
        self._keepalive.allow()

    def allow(self):
        if not self._keepalive:
            raise EstopError('no estop endpoint is active')
        self._keepalive.allow()

    def stop(self):
        if not self._keepalive:
            raise EstopError('no estop endpoint is active')
        self._keepalive.stop()

    def settle_then_cut(self):
        if not self._keepalive:
            raise EstopError('no estop endpoint is active')
        self._keepalive.settle_then_cut()

    def shutdown(self):
        if not self._keepalive:
            raise EstopError('no estop endpoint is active')
        # todo: handle error for no endpoint registered?
        self._keepalive.shutdown()
        self._endpoint = None
        self._keepalive = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        # why not shutdown? this is what the BD examples do
        if self._keepalive:
            self._keepalive.end_periodic_check_in()
