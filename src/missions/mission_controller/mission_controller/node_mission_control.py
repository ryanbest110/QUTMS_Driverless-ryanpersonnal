from ament_index_python import get_package_share_directory
from ros2launch.api.api import launch_a_launch_file

import rclpy
from rclpy.node import Node

from driverless_msgs.msg import State

from driverless_msgs.srv import SelectMission

from .mission_constants import INT_MISSION_TYPE

mission_pkg = get_package_share_directory("missions")  # path to the missions package


class MissionControl(Node):
    target_mission: str = "inspection"  # default mission
    mission_launched: bool = False

    def __init__(self):
        super().__init__("mission_control")

        self.create_subscription(State, "/ros_state", 10)

        self.create_service(SelectMission, "select_mission", self.gui_srv)

        self.get_logger().info("---Mission Control node initialised---")

    def gui_srv(self, request, response):  # service callback from terminal selection
        self.get_logger().info("Selected: " + request.mission)
        if request.mission != "R2D":
            self.target_mission = request.mission
            launch_a_launch_file(
                launch_file_path=(mission_pkg + "/" + self.target_mission + ".launch.py"), launch_file_arguments={}
            )
            return response

    def callback(self, status: State):
        if status.mission != State.MISSION_NONE and not self.mission_launched:
            self.target_mission = INT_MISSION_TYPE[status.mission].value
            self.get_logger().info("Mission started: " + str(self.target_mission))
            self.mission_launched = True
            launch_a_launch_file(
                launch_file_path=(mission_pkg + "/" + self.target_mission + ".launch.py"), launch_file_arguments={}
            )


def main(args=None):
    rclpy.init(args=args)
    node = MissionControl()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()