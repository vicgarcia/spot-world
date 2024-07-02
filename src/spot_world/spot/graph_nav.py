import logging
import pathlib
import time
import collections
import os
import math
from bosdyn.client.exceptions import ResponseError
from bosdyn.client.graph_nav import GraphNavClient
from bosdyn.client.frame_helpers import get_odom_tform_body
from bosdyn.api.graph_nav import graph_nav_pb2, map_pb2, nav_pb2

logger = logging.getLogger(__name__)


class GraphNavError(Exception):
    pass


class Map:

    def __init__(self, graph: map_pb2.Graph, waypoint_snapshots, edge_snapshots):
        self.graph = graph
        # waypoint_snapshots is dict of waypoint snapshot id -> map_pb2.WaypointSnapshot
        self.waypoint_snapshots = waypoint_snapshots
        # edge_snapshots is a dict of edge snapshot id -> map_pb2.EdgeSnapshot
        self.edge_snapshots = edge_snapshots
        # # setup a dict of waypoint id -> waypoint name
        # self.waypoint_names = {w.id: w.annotations.name for w in self.graph.waypoints}

    # based on the assumption that a graph is created via autowalk
    # and that the first (by timestamp) waypoint is the begining of the mission

    @property
    def first_waypoint(self):
        if len(self.graph.waypoints) == 0:
            return None
        first_waypoint = sorted(self.graph.waypoints, key=lambda w: w.annotations.creation_time.seconds)[0]
        return first_waypoint

    def shortest_path(self, start_waypoint_id, end_waypoint_id):
        ''' returns list of waypoint ids for shortest path between start and end '''
        # https://onestepcode.com/graph-shortest-path-python/
        graph = collections.defaultdict(set)
        for edge in self.graph.edges:
            graph[edge.id.from_waypoint].add(edge.id.to_waypoint)
            graph[edge.id.to_waypoint].add(edge.id.from_waypoint)
        paths, index = [[start_waypoint_id]], 0
        previous_waypoints = {start_waypoint_id}
        if start_waypoint_id == end_waypoint_id:
            return paths[0]
        while index < len(paths):
            current_path = paths[index]
            last_waypoint = current_path[-1]
            next_waypoints = graph[last_waypoint]
            if end_waypoint_id in next_waypoints:
                current_path.append(end_waypoint_id)
                return current_path
            for next_waypoint in next_waypoints:
                if not next_waypoint in previous_waypoints:
                    new_path = current_path[:]
                    new_path.append(next_waypoint)
                    previous_waypoints.add(next_waypoint)
            index += 1
        return []

    def get_fiducials(self):
        fiducials = set()
        for waypoint in self.graph.waypoints:
            snapshot = self.waypoint_snapshots[waypoint.snapshot_id]
            for potential_fiducial in snapshot.objects:
                if potential_fiducial.HasField('apriltag_properties'):
                    fiducial_number = potential_fiducial.apriltag_properties.tag_id
                    fiducials.add(fiducial_number)
        return list(fiducials)

    def _calc_distance_from_origin(self, x, y, z):
        # https://www.math.usm.edu/lambers/mat169/fall09/lecture17.pdf
        return math.sqrt(x ** 2 + y ** 2 + z ** 2)

    def get_waypoint_id_by_fiducial(self, search_fiducial: int):
        # find the closest waypoint to the fiducial
        distances_and_waypoints = []
        # iterate over the waypoints on the map and get the snapshots
        for waypoint in self.graph.waypoints:
            snapshot = self.waypoint_snapshots[waypoint.snapshot_id]
            # iterate over the objects in the snapshot and check for fiducial in objects
            for snapshot_object in snapshot.objects:
                if snapshot_object.HasField('apriltag_properties'):
                    if snapshot_object.apriltag_properties.tag_id == search_fiducial:
                        # get x,y,z to calc distance to fiducial from body at waypoint
                        transform = snapshot_object.transforms_snapshot \
                            .child_to_parent_edge_map.get(f'fiducial_{search_fiducial}')
                        x = transform.parent_tform_child.position.x
                        y = transform.parent_tform_child.position.y
                        z = transform.parent_tform_child.position.z
                        # calc distance to fiducial
                        distance = self._calc_distance_from_origin(x, y, z)
                        # when this is a docking fiducial exclude distance less than 1
                        # this will prevent selecting a waypoint on top of the dock
                        if search_fiducial >= 500:
                            if distance < 1.0:
                                continue
                        distances_and_waypoints.append(
                            (distance, waypoint.id)
                        )
        # return None when the fiducial wasn't found
        if len(distances_and_waypoints) == 0:
            return None
        distance, waypoint_id = sorted(distances_and_waypoints)[0]
        return waypoint_id

    @classmethod
    def from_filesystem(cls, base_path: pathlib.Path):
        # expect the base path to be the folder from a autowalk from tablet
        graph_path = pathlib.Path(base_path, 'graph')
        if not graph_path.exists():
            raise GraphNavClient(f"graph file {graph_path} not found")
        graph = map_pb2.Graph()
        with open(graph_path, 'rb') as graph_file:
            graph.ParseFromString(graph_file.read())
        waypoint_snapshots = {}
        for waypoint in graph.waypoints:
            if len(waypoint.snapshot_id) == 0:
                continue
            waypoint_snapshot_path = pathlib.Path(base_path, 'waypoint_snapshots', waypoint.snapshot_id)
            if not waypoint_snapshot_path.exists():
                raise GraphNavClient(f"waypoint snapshot file {waypoint_snapshot_path} not found")
            waypoint_snapshot = map_pb2.WaypointSnapshot()
            with open(waypoint_snapshot_path, 'rb') as waypoint_snapshot_file:
                waypoint_snapshot.ParseFromString(waypoint_snapshot_file.read())
            waypoint_snapshots[waypoint.snapshot_id] = waypoint_snapshot
        edge_snapshots = {}
        for edge in graph.edges:
            if len(edge.snapshot_id) == 0:
                continue
            edge_snapshot_path = pathlib.Path(base_path, 'edge_snapshots', edge.snapshot_id)
            if not edge_snapshot_path.exists():
                raise GraphNavClient(f"edge snapshot file {edge_snapshot_path} not found")
            edge_snapshot = map_pb2.EdgeSnapshot()
            with open(edge_snapshot_path, 'rb') as edge_snapshot_file:
                edge_snapshot.ParseFromString(edge_snapshot_file.read())
            edge_snapshots[edge.snapshot_id] = edge_snapshot
        return cls(graph, waypoint_snapshots, edge_snapshots)


class GraphNavFacade:

    def __init__(self, spot):
        self._spot = spot

    @property
    def client(self):
        return self._spot._robot.ensure_client(GraphNavClient.default_service_name)

    def clear(self):
        self.client.clear_graph()

    def upload_map(self, map: Map):
        generate_new_anchoring = not len(map.graph.anchoring.anchors)
        response = self.client.upload_graph(
            graph=map.graph,
            generate_new_anchoring=generate_new_anchoring,
        )
        for snapshot_id in response.unknown_waypoint_snapshot_ids:
            waypoint_snapshot = map.waypoint_snapshots[snapshot_id]
            self.client.upload_waypoint_snapshot(waypoint_snapshot)
        for snapshot_id in response.unknown_edge_snapshot_ids:
            edge_snapshot = map.edge_snapshots[snapshot_id]
            self.client.upload_edge_snapshot(edge_snapshot)

    def download_map(self):
        graph = self.client.download_graph()
        if graph is None:
            raise GraphNavClient('download of graph failed')
        waypoint_snapshots = {}
        for waypoint in graph.waypoints:
            if len(waypoint.snapshot_id) == 0:
                continue
            waypoint_snapshot = self.client.download_waypoint_snapshot(waypoint.snapshot_id)
            waypoint_snapshots[waypoint.snapshot_id] = waypoint_snapshot
        edge_snapshots = {}
        for edge in graph.edges:
            if len(edge.snapshot_id) == 0:
                continue
            edge_snapshot = self.client.download_edge_snapshot(edge.snapshot_id)
            edge_snapshots[edge.snapshot_id] = edge_snapshot
        return Map(graph, waypoint_snapshots, edge_snapshots)

    def localize_to_fiducial(self):
        robot_state = self._spot.robot_state.get()
        current_odom_tform_body = get_odom_tform_body(robot_state.kinematic_state.transforms_snapshot)
        localization = nav_pb2.Localization()
        self.client.set_localization(
            initial_guess_localization=localization,
            ko_tform_body=current_odom_tform_body.to_proto(),
        )

    def navigate_to_waypoint(self, waypoint_id):
        navigation_complete = False
        while not navigation_complete:
            navigation_command = None
            try:
                navigation_command = self.client.navigate_to(waypoint_id, 1.0,
                    leases=[self._spot.lease.current],
                    command_id=navigation_command
                )
            except ResponseError as e:
                return False
            time.sleep(.5)
            navigation_complete = self._check_success(navigation_command)
        return True

    def _check_success(self, command=-1):
        if command == -1:
            return False
        feedback = self.client.navigation_feedback(command)
        if feedback.status == graph_nav_pb2.NavigationFeedbackResponse.STATUS_REACHED_GOAL:
            return True
        # todo: handle other possible statuses here?
        else:
            return False
