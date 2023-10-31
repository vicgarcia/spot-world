import logging
from bosdyn.client.power import PowerClient
from bosdyn.api.robot_state_pb2 import PowerState

logger = logging.getLogger(__name__)


class PowerError(Exception):
    pass


class PowerStatus:
    ON = 'ON'
    OFF = 'OFF'


class PowerFacade:

    def __init__(self, spot):
        self._spot = spot

    @property
    def client(self):
        return self._spot._robot.ensure_client(PowerClient.default_service_name)

    @property
    def status(self):
        power_state = self._spot.robot_state.client.get_robot_state().power_state
        if power_state.motor_power_state == PowerState.STATE_ON:
            return PowerStatus.ON
        return PowerStatus.OFF

    def on(self):
        self._spot._robot.power_on(timeout_sec=30)

    def off(self):
        self._spot._robot.power_off(cut_immediately=False, timeout_sec=30)
