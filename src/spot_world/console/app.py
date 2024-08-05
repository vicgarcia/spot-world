import logging
import cmd2
import sys
import os
import argparse
import pathlib
import time
from dotenv import load_dotenv
from types import FrameType
from spot_world.spot import Spot
from spot_world.spot.estop import EstopStatus
from spot_world.spot.lease import LeaseError, LeaseStatus
from spot_world.spot.power import PowerStatus
from spot_world.spot.autowalk import Mission
from spot_world.spot.graph_nav import Map

logger = logging.getLogger(__name__)


class App(cmd2.Cmd):

    def __init__(self, spot: Spot, autowalk_path: pathlib.Path, initialize_robot=False):
        # setup cmd2 app
        cmd2.Cmd.__init__(self, include_py=True)
        self._cleanup_features()
        # autowalk_path is validated in the run() factory method
        self.autowalk_path = autowalk_path
        # attach the robot
        self.spot = spot
        # load the map
        self.map = Map.from_filesystem(autowalk_path)
        # upload map to the robot
        self.spot.graph_nav.clear()
        self.spot.graph_nav.upload_map(self.map)
        # optionally initialize the robot
        if initialize_robot:
            self._initialize_robot()
        # dock_id to be set when undocking
        self.dock_id = None
        # export these for use in the python shell
        self.py_locals = {
            'spot': self.spot,
            'map': self.map,
        }
        # setup custom prompt
        self._set_prompt()

    def _cleanup_features(self):
        # remove unused features from the cmd2 base application
        delattr(cmd2.Cmd, 'do_shell')
        delattr(cmd2.Cmd, 'do_edit')
        delattr(cmd2.Cmd, 'do_shortcuts')
        delattr(cmd2.Cmd, 'do_run_script')
        delattr(cmd2.Cmd, 'do_run_pyscript')
        self.hidden_commands += [ 'alias', 'history', 'macro', 'set' ]

    def _initialize_robot(self):
        # setup estop
        self.spot.estop.setup()
        # acquire lease
        self.spot.lease.take()
        # power on motors
        self.spot.power.on()

    _motor_status_color = {
        PowerStatus.OFF: cmd2.ansi.Fg.WHITE,
        PowerStatus.ON: cmd2.ansi.Fg.GREEN,
    }

    _lease_status_color = {
        LeaseStatus.NONE: cmd2.ansi.Fg.WHITE,
        LeaseStatus.ACTIVE: cmd2.ansi.Fg.GREEN,
    }

    _estop_status_color = {
        EstopStatus.ERROR: cmd2.ansi.Fg.YELLOW,
        EstopStatus.NONE: cmd2.ansi.Fg.WHITE,
        EstopStatus.ESTOPPED: cmd2.ansi.Fg.RED,
        EstopStatus.NOT_ESTOPPED: cmd2.ansi.Fg.GREEN,
    }

    def _battery_status_color(self, battery_level: int):
        if battery_level > 30:
            return cmd2.ansi.Fg.GREEN
        elif battery_level > 10:
            return cmd2.ansi.Fg.YELLOW
        else:
            return cmd2.ansi.Fg.RED

    def _set_prompt(self):
        # new line before prompt
        p = '\n'
        # lease indicator
        p += cmd2.ansi.style("LEASE", fg=self._lease_status_color[self.spot.lease.status])
        p += ' '
        # estop indicator
        p += cmd2.ansi.style(f"ESTOP", fg=self._estop_status_color[self.spot.estop.status])
        p += ' '
        # motor power indicator
        p += cmd2.ansi.style(f"MOTOR", fg=self._motor_status_color[self.spot.power.status])
        p += ' '
        # battery indicator
        battery_level = self.spot.power.battery
        p += cmd2.ansi.style(f"{battery_level}%", fg=self._battery_status_color(battery_level))
        p += ' # '
        # assign string to prompt
        self.prompt = p

    def postcmd(self, stop, line):
        self._set_prompt()
        return stop

    def _exit(self):
        ''' exit the application '''
        # respond to 'exit' or 'quit'
        try:
            self.spot.robot_command.sit()
            self.spot.power.off()
            self.spot.estop.shutdown()
            self.spot.lease.release()
        except Exception:
            pass
        # Return True to stop the command loop
        self.last_result = True
        return True

    def do_exit(self, *args, **kwargs):
        return self._exit()

    def do_quit(self, *args, **kwargs):
        return self._exit()

    _estop_parser = cmd2.Cmd2ArgumentParser()
    _estop_command_choices = ['setup', 'shutdown', 'clear']
    _estop_parser.add_argument('command', choices=_estop_command_choices, help='manage estop for robot')

    @cmd2.with_argparser(_estop_parser)
    def do_estop(self, args):
        ''' manage robot estop '''
        # starts estop keepalive
        if args.command == 'setup':
            self.spot.estop.setup()
        # stops estop keepalive
        elif args.command == 'shutdown':
            self.spot.estop.shutdown()
        # clear estop after engaging with ctrl-c
        elif args.command == 'clear':
            self.spot.estop.allow()

    def sigint_handler(self, signum: int, _: FrameType) -> None:
        # override default sigint to use ctrl-c to engage the estop
        if self.spot.estop.status != EstopStatus.NONE:
            self.poutput('\nengaging estop')
            self.spot.estop.settle_then_cut()
            # wait for robot status to update for the prompt
            time.sleep(2)
            # update the prompt to ensure the estop status is reflected
            self._set_prompt()
        return super().sigint_handler(signum, _)

    def do_status(self, args):
        # get data from robot state query and print to terminal
        state = self.spot.robot_state.get()
        self.poutput(state)

    _lease_parser = cmd2.Cmd2ArgumentParser()
    _lease_action_choices = ['acquire', 'take', 'release']
    _lease_parser.add_argument('command', choices=_lease_action_choices, help='manage lease for robot')

    @cmd2.with_argparser(_lease_parser)
    def do_lease(self, args):
        ''' manage robot lease '''
        try:
            if args.command == 'acquire':
                self.spot.lease.acquire()
            elif args.command == 'take':
                self.spot.lease.take()
            elif args.command == 'release':
                self.spot.lease.release()
        except LeaseError as e:
            self.poutput(str(e))

    _motors_parser = cmd2.Cmd2ArgumentParser()
    _motors_command_choices = ['on', 'off']
    _motors_parser.add_argument('command', choices=_motors_command_choices, help='manage robot motors on/off')

    @cmd2.with_argparser(_motors_parser)
    def do_motors(self, args):
        ''' manage robot motor power '''
        if args.command == 'on':
            self.spot.power.on()
        elif args.command == 'off':
            self.spot.power.off()

    _robot_parser = cmd2.Cmd2ArgumentParser()
    _robot_command_choices = ['stand', 'sit', 'undock', 'dock', 'return', 'localize']
    _robot_parser.add_argument('command', choices=_robot_command_choices, help='command the robot')

    @cmd2.with_argparser(_robot_parser)
    def do_robot(self, args):
        ''' command the robot '''
        if args.command == 'stand':
            self.spot.robot_command.stand()
        elif args.command == 'sit':
            self.spot.robot_command.sit()
        elif args.command == 'undock':
            dock_id = self.spot.docking.get_dock_id()
            if dock_id:
                self.dock_id = dock_id
                self.spot.docking.undock()
                self.spot.graph_nav.localize_to_fiducial()
            else:
                self.poutput(f"robot is not currently docked")
        elif args.command == 'dock':
            # todo : specify dock when multiple are visible?
            docks = self.spot.world_object.get_visible_docks()
            if len(docks) == 0:
                self.poutput('no visible dock')
            self.spot.docking.dock(docks[0])
        elif args.command == 'return':
            if self.dock_id:
                waypoint_id = self.map.get_waypoint_id_by_fiducial(self.dock_id)
                self.spot.graph_nav.navigate_to_waypoint(waypoint_id)
                self.spot.docking.dock(self.dock_id)
            else:
                self.poutput("no dock_id stored to return to")
        elif args.command == 'localize':
            self.spot.graph_nav.localize_to_fiducial()

    # the idea of 'goto fiducial' was the original purpose of spot world
    # before spot world ever ran missions, it simply navigated to fiducials

    _fiducials_parser = cmd2.Cmd2ArgumentParser()
    _fiducials_subparser = _fiducials_parser.add_subparsers(title='subcommands', help='mission subcommands help')

    def fiducials_list(self, args):
        ''' list available fiducials on loaded map '''
        fiducials = self.map.get_fiducials()
        for f in fiducials:
            self.poutput(f"{f}")
        self.map.get_waypoint_id_by_fiducial(fiducials[0])

    _fiducials_list_parser = _fiducials_subparser.add_parser('list', help='list fiducials on the loaded map')
    _fiducials_list_parser.set_defaults(func=fiducials_list)

    def fiducials_goto(self, args):
        ''' goto a fiducial '''
        waypoint_id = self.map.get_waypoint_id_by_fiducial(args.fiducial)
        if not waypoint_id:
            self.poutput(f"could not find position for fiducial {args.fiducial}")
        self.spot.graph_nav.navigate_to_waypoint(waypoint_id)

    _fiducials_goto_parser = _fiducials_subparser.add_parser('goto', help='move to a fiducial')
    _fiducials_goto_parser.add_argument('fiducial', type=int, help='number of fidcuial to goto')
    _fiducials_goto_parser.set_defaults(func=fiducials_goto)

    @cmd2.with_argparser(_fiducials_parser)
    def do_fiducials(self, args):
        ''' interact with fiducials'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('fiducials')

    _missions_parser = cmd2.Cmd2ArgumentParser()
    _missions_subparser = _missions_parser.add_subparsers(title='subcommands', help='missions subcommands help')

    def missions_list(self, args):
        missions_path = self.autowalk_path / 'missions'
        for mission in missions_path.glob('*.walk'):
            # exclude the .walk extension from the listings
            self.poutput(mission.stem.replace('.walk', ''))

    _missions_list_parser = _missions_subparser.add_parser('list', help='list available missions')
    _missions_list_parser.set_defaults(func=missions_list)

    def missions_execute(self, args):
        try:
            mission = Mission.from_filesystem(self.autowalk_path, f"{' '.join(args.name)}.walk")
            mission.skip_docking()  # when running missions via spot console we skip docking by default
            self.spot.autowalk.upload_mission(mission)
            # when the robot is docked when the mission is run
            # keep the dock id and return when mission complete
            dock_id = self.spot.docking.get_dock_id()
            if dock_id:
                self.dock_id = dock_id
                self.spot.docking.undock()
                self.spot.graph_nav.localize_to_fiducial()
            self.spot.mission.run()
            # if the robot was docked when the mission was started, return to the dock
            if dock_id:
                waypoint_id = self.map.get_waypoint_id_by_fiducial(dock_id)
                self.spot.graph_nav.navigate_to_waypoint(waypoint_id)
                self.spot.docking.dock(dock_id)
        except Exception as e:
            self.poutput(str(e))

    _missions_execute_parser = _missions_subparser.add_parser('execute', help='load and run a mission')
    _missions_execute_parser.add_argument('name', nargs='+', type=str, help='name of mission to execute')
    _missions_execute_parser.set_defaults(func=missions_execute)

    def missions_loop(self, args):
        try:
            mission = Mission.from_filesystem(self.autowalk_path, f"{' '.join(args.name)}.walk")
            mission.skip_docking()  # when running missions via spot console we skip docking
            self.spot.autowalk.upload_mission(mission)
            # when the robot is docked when the loop starts
            # keep the dock id and return when mission complete
            dock_id = self.spot.docking.get_dock_id()
            if dock_id:
                self.dock_id = dock_id
                self.spot.docking.undock()
                self.spot.graph_nav.localize_to_fiducial()
            # run the mission on a loop
            # the only exit here is engaging the estop then manually assuming control
            while True:
                self.spot.mission.run()
                # reload mission to run again
                self.spot.autowalk.upload_mission(mission)
        except Exception as e:
            self.poutput(str(e))

    _missions_loop_parser = _missions_subparser.add_parser('loop', help='load and run a mission on a loop')
    _missions_loop_parser.add_argument('name', nargs='+', type=str, help='name of mission to execute')
    _missions_loop_parser.set_defaults(func=missions_loop)

    @cmd2.with_argparser(_missions_parser)
    def do_missions(self, args):
        ''' manage missions '''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('missions')

    @classmethod
    def run(cls):

        # get values from .env
        load_dotenv()
        hostname = os.getenv('SPOT_HOSTNAME')
        username = os.getenv('SPOT_USERNAME')
        password = os.getenv('SPOT_PASSWORD')

        # parse arguments
        parser = argparse.ArgumentParser(description='console for controlling SPOT')
        parser.add_argument('--hostname',
            help='ip/hostname of spot robot',
            required=hostname == None,
        )
        parser.add_argument('--username',
            help='username to authenticate to spot',
            required=username == None,
        )
        parser.add_argument('--password',
            help='password to authenticate to spot',
            required=password == None,
        )
        parser.add_argument('--autowalk',
            help='directory containing autowalk to load',
            nargs='+',
            required=True,
        )
        parser.add_argument('--initialize',
            help='enable initialize robot on startup',
            action='store_true',
        )
        args = parser.parse_args(sys.argv[1:])

        # overwrite env values with cli args
        if args.hostname:
            hostname = args.hostname
        if args.username:
            username = args.username
        if args.password:
            password = args.password

        # expect a path to an autowalk map and set of missions
        # this is the .walk folder and it's contents from the tablet
        # validate the path here and fail w/ error message
        autowalk_path = pathlib.Path(' '.join(args.autowalk)).resolve()
        if not autowalk_path.exists():
            print(f"{autowalk_path} does not exist")
            sys.exit(1)

        # connect to robot
        spot = Spot.connect(hostname, username, password)

        # clear startup arguments so they aren't passed into cmd2 app
        sys.argv = sys.argv[:1]

        # start app
        app = cls(spot, autowalk_path, initialize_robot=args.initialize)
        sys.exit(app.cmdloop())
