import logging
import pathlib
from bosdyn.api.autowalk import autowalk_pb2, walks_pb2
from bosdyn.client.autowalk import AutowalkClient
from spot_world.spot.graph_nav import Map

logger = logging.getLogger(__name__)


class Mission:

    def __init__(self, walk: walks_pb2.Walk):
        self.walk = walk

    def skip_docking(self):
        self.walk.playback_mode.once.skip_docking_after_completion = True

    @classmethod
    def from_filesystem(cls, autowalk_path: pathlib.Path, mission_file: str):
        # check if the autowalk path exists
        if not autowalk_path.exists():
            raise AutowalkError(f"autowalk path not found {autowalk_path}")
        # check if the mission file exists
        mission_path = autowalk_path / 'missions' / mission_file
        if not mission_path.exists():
            raise AutowalkError(f"mission path not found {mission_path}")
        # load the autowalk mission
        walk = walks_pb2.Walk()
        with open(mission_path, 'rb') as mission_file:
            walk.ParseFromString(mission_file.read())
        # return mission
        return cls(walk)


class AutowalkError(Exception):
    pass


class AutowalkFacade:

    def __init__(self, spot):
        self._spot = spot

    @property
    def client(self):
        return self._spot._robot.ensure_client(AutowalkClient.default_service_name)

    def upload_mission(self, mission: Mission):
        autowalk_result = self.client.load_autowalk(mission.walk)
        if not autowalk_result.status == autowalk_pb2.LoadAutowalkResponse.STATUS_OK:
            raise AutowalkError('failed to upload mission')
