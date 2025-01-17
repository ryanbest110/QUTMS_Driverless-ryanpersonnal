import rclpy
from rclpy.node import Node
from rclpy.publisher import Publisher

from driverless_msgs.msg import Reset, Shutdown

from driverless_common.shutdown_node import ShutdownNode


class InspectionMission(ShutdownNode):
    started: bool = False

    def __init__(self):
        super().__init__("inspection_logic_node")
        self.timer = self.create_timer(30, self.timer_callback)
        self.shutdown_pub: Publisher = self.create_publisher(Shutdown, "/system/shutdown", 1)
        self.reset_sub = self.create_subscription(Reset, "/system/reset", self.reset_callback, 10)

        self.get_logger().info("---Inspection mission initialised---")

    def reset_callback(self, msg: Reset):
        self.timer.reset()
        self.started = True

    def timer_callback(self):
        if self.started:
            shutdown_msg = Shutdown(finished_engage_ebs=True)
            self.shutdown_pub.publish(shutdown_msg)


def main(args=None):
    rclpy.init(args=args)
    node = InspectionMission()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
