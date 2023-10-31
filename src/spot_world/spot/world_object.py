import logging
from bosdyn.client.world_object import WorldObjectClient
from bosdyn.api import world_object_pb2

logger = logging.getLogger(__name__)


class WorldObjectFacade:

    def __init__(self, spot):
        self._spot = spot

    @property
    def client(self):
        return self._spot._robot.ensure_client(WorldObjectClient.default_service_name)

    def get_visible_fiducials(self):
        request_fiducials = [world_object_pb2.WORLD_OBJECT_APRILTAG]
        fiducial_objects = self.client.list_world_objects(object_type=request_fiducials).world_objects
        return fiducial_objects

    def get_visible_docks(self):
        fiducial_objects = self.get_visible_fiducials()
        visible_docks = []
        for fiducial_object in fiducial_objects:
            fiducial_number = int(fiducial_object.apriltag_properties.tag_id)
            # docks have fiducials with ids 500 and up
            if fiducial_number >= 500:
                visible_docks.append(fiducial_number)
        return visible_docks
