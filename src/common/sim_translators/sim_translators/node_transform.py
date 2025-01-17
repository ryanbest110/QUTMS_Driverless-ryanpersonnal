from tf2_ros import TransformBroadcaster

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry


class TF2Publisher(Node):
    def __init__(self):
        super().__init__("sim_transform_publisher")

        # Initialize the transform broadcaster
        self.broadcaster = TransformBroadcaster(self)

        # callback function on each message
        self.create_subscription(Odometry, "/fsds/testing_only/odom", self.callback, 1)

    def callback(self, msg: Odometry):
        t = TransformStamped()
        # Read message content and assign it to
        # corresponding tf variables
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = "simmap"
        t.child_frame_id = "simcar"

        t.transform.translation.x = msg.pose.pose.position.x
        t.transform.translation.y = msg.pose.pose.position.y
        t.transform.translation.z = msg.pose.pose.position.z
        t.transform.rotation = msg.pose.pose.orientation

        # Send the transformation
        self.broadcaster.sendTransform(t)


def main():
    rclpy.init()
    node = TF2Publisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
