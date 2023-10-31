import logging
from bosdyn.client.robot_command import RobotCommandClient, RobotCommandBuilder

logger = logging.getLogger(__name__)


class RobotCommandError:
    pass


class RobotCommandFacade:

    def __init__(self, spot):
        self._spot = spot

    @property
    def client(self):
        return self._spot._robot.ensure_client(RobotCommandClient.default_service_name)

    def _try_grpc(self, desc, thunk):
        try:
            # a 'thunk' is a piece of machine generated code
            return thunk()
        except Exception as err:
        # except (ResponseError, RpcError, LeaseBaseError) as err:
            # todo: handle an error here, use desc in output message
            return None

    def _start_robot_command(self, desc, command_proto, end_time_secs=None):
        def _start_command():
            self.client.robot_command(lease=None, command=command_proto, end_time_secs=end_time_secs)
        self._try_grpc(desc, _start_command)

    def stand(self):
        self._start_robot_command('stand', RobotCommandBuilder.synchro_stand_command())

    def sit(self):
        self._start_robot_command('sit', RobotCommandBuilder.synchro_sit_command())
