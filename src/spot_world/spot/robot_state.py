import logging
from bosdyn.client.robot_state import RobotStateClient

logger = logging.getLogger(__name__)


class RobotStateFacade:

    def __init__(self, spot):
        self._spot = spot

    @property
    def client(self):
        return self._spot._robot.ensure_client(RobotStateClient.default_service_name)

    def get(self):
        return self.client.get_robot_state()
