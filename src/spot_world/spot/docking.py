import logging
from bosdyn.client.docking import DockingClient, blocking_dock_robot, blocking_undock, get_dock_id

logger = logging.getLogger(__name__)


class DockingError(Exception):
    pass


class DockingStatus:
    DOCKED = 'DOCKED'
    UNDOCKED = 'UNDOCKED'


class DockingFacade:

    def __init__(self, spot):
        self._spot = spot

    @property
    def client(self):
        return self._spot._robot.ensure_client(DockingClient.default_service_name)

    def get_dock_id(self):
        # returns None when not docked
        return get_dock_id(self._spot._robot)

    @property
    def status(self):
        if get_dock_id(self._spot._robot) is not None:
            return DockingStatus.DOCKED
        return DockingStatus.UNDOCKED

    def is_docked(self):
        return get_dock_id(self._spot._robot) is not None

    def undock(self):
        blocking_undock(self._spot._robot)

    def dock(self, dock_id):
        blocking_dock_robot(self._spot._robot, dock_id)
