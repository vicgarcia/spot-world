import logging
import bosdyn.client
import bosdyn.mission.client
from spot_world.spot.power import PowerFacade
from spot_world.spot.robot_state import RobotStateFacade
from spot_world.spot.estop import EstopFacade
from spot_world.spot.lease import LeaseFacade
from spot_world.spot.robot_command import RobotCommandFacade
from spot_world.spot.docking import DockingFacade
from spot_world.spot.graph_nav import GraphNavFacade
from spot_world.spot.world_object import WorldObjectFacade
from spot_world.spot.mission import MissionFacade
from spot_world.spot.autowalk import AutowalkFacade

logger = logging.getLogger(__name__)


class Spot:

    def __init__(self, robot):
        self._robot = robot
        self.robot_state = RobotStateFacade(self)
        self.estop = EstopFacade(self)
        self.lease = LeaseFacade(self)
        self.power = PowerFacade(self)
        self.robot_command = RobotCommandFacade(self)
        self.docking = DockingFacade(self)
        self.graph_nav = GraphNavFacade(self)
        self.world_object = WorldObjectFacade(self)
        self.mission = MissionFacade(self)
        self.autowalk = AutowalkFacade(self)

    @property
    def name(self):
        # replace periods w/ dashes for cleaner robot name (by ip) to file name
        return self._robot._name.replace('.', '-')

    @property
    def hostname(self):
        return self._robot._name

    # figure out where to get serial and nickname

    @classmethod
    def connect(cls, hostname, username, password):
        sdk = bosdyn.client.create_standard_sdk('spot-world', [
            bosdyn.mission.client.MissionClient
        ])
        robot = sdk.create_robot(hostname)
        robot.authenticate(username, password)
        robot.time_sync.wait_for_sync()
        return cls(robot)
