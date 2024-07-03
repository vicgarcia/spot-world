import logging
import pathlib
import time
import bosdyn.mission.client
from bosdyn.client.exceptions import RpcError, ResponseError
from bosdyn.api.mission import mission_pb2
from bosdyn.api.mission import nodes_pb2
from spot_world.spot.graph_nav import Map

logger = logging.getLogger(__name__)


class MissionError(Exception):
    pass


class MissionStatus:
    NONE = 'NONE'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    # we aren't implementing handling for mission questions
    # so we fail on this with a useful enough status
    FAILED_ON_QUESTION = 'FAILED_ON_QUESTION'


class MissionFacade:

    def __init__(self, spot):
        self._spot = spot
        self._last_status = MissionStatus.NONE

    @property
    def client(self):
        return self._spot._robot.ensure_client(bosdyn.mission.client.MissionClient.default_service_name)

    @property
    def status(self):
        return self._last_status

    def run(self, mission_timeout=30, disable_directed_exploration=True):
        mission_state = self.client.get_state()
        logger.debug(f"initial mission state {mission_state}")
        while mission_state.status in (mission_pb2.State.STATUS_NONE, mission_pb2.State.STATUS_RUNNING):
            self._last_status = MissionStatus.RUNNING
            if mission_state.questions:
                # fail the mission unless we can handle the question w/o user input
                question_fails_mission = True
                for question in mission_state.questions:
                    # todo: for now we ignore any questions w/ SEVERITY_LEVEL_INFO
                    #       in the future we could either automatically act or prompt user
                    if question.severity == 1:  # SEVERITY_LEVEL_INFO
                        question_fails_mission = False
                if question_fails_mission:
                    logger.debug(f"fail mission due to spot question prompt")
                    return MissionStatus.FAILED_ON_QUESTION
            local_pause_time = time.time() + mission_timeout
            body_lease = self._spot.lease.client.lease_wallet.advance()
            mission_settings = mission_pb2.PlaySettings(
                disable_directed_exploration=disable_directed_exploration,
            )
            self.client.play_mission(local_pause_time, [body_lease], mission_settings)
            time.sleep(1)
            mission_state = self.client.get_state()
        logger.debug(f"last mission state {mission_state}")
        if mission_state.status == mission_pb2.State.STATUS_SUCCESS:
            return MissionStatus.SUCCESS
        else:
            return MissionStatus.FAILURE
