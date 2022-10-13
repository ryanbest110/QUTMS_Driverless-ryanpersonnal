import time

import rclpy
from rclpy.node import Node
from ament_index_python import get_package_share_directory
from ros2launch.api.api import launch_a_launch_file 

from driverless_msgs.msg import Can, Reset, State

from driverless_msgs.srv import SelectMission

from .mission_constants import CAN_TO_MISSION_TYPE


mission_pkg = get_package_share_directory("missions")  # path to the missions package
# ts_controller_pkg = get_package_share_directory("tractive_system_controller")  # path to the tractive_system_controller package    

class MissionControl(Node):
    target_mission: str = "inspection"  # default mission

    def __init__(self):
        super().__init__("mission_control")

        self.create_subscription(Can, "/can_rosbound", self.callback, 10)

        self.publisher = self.create_publisher(State, "/state", 10)
        self.publisher = self.create_publisher(Reset, "/reset", 10)

        self.create_service(SelectMission, "select_mission", self.gui_srv)

        self.get_logger().info("---Mission Control node initialised---")
        
    def gui_srv(self, request, response):  # service callback from terminal selection
        self.get_logger().info("Selected mission: " + request.mission)
        self.target_mission = request.mission       
        launch_a_launch_file(launch_file_path=(mission_pkg + "/" + self.target_mission + ".launch.py"), launch_file_arguments={})
        return response

    def callback(self, can_msg: Can):
        # first, listen to CAN steering wheel buttons to select mission from steering wheel display
        # check for ID of steering wheel data
        # save target mission
        if can_msg.data == "mission_selection":  # idk about what can IDs are
            mission: int = can_msg.data  # extract msg data
            if mission in CAN_TO_MISSION_TYPE:  # check if its an actual value
                self.target_mission = CAN_TO_MISSION_TYPE[mission]
                launch_a_launch_file(launch_file_path=(mission_pkg + "/" + self.target_mission + ".launch.py"), launch_file_arguments={})
        
        if can_msg.data == "ready_to_drive":
            self.get_logger().info("Ready to drive")
            self.publisher.publish(State(r2d=True))
            self.publisher.publish(Reset(reset=True))

            # launch_a_launch_file(ts_controller_pkg + "/ts_controller.launch.py")


def main(args=None):
    rclpy.init(args=args)
    node = MissionControl()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
