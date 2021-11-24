import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge

import cv2
import numpy as np

from .threshold import Threshold
from .hsv_cv import get_coloured_objects
from .rect import Rect, draw_box

from typing import Optional


cv_bridge = CvBridge()


LEFT_THRESH = Threshold(
    lower=[55, 170, 0],
    upper=[65, 255, 255],
)
LEFT_DISP_COLOUR = (255, 0, 0)  # bgr - blue

RIGHT_THRESH = Threshold(
    lower=[55, 170, 0],
    upper=[65, 255, 255],
)
RIGHT_DISP_COLOUR = (0, 255, 255)  # bgr - yellow


class ControllerNode(Node):
    def __init__(self):
        super().__init__("controller")
        self.create_subscription(
            Image,
            "/zed2i/zed_node/left/image_rect_color",
            self.image_callback,
            10,
        )
        self.get_logger().info("Controller Node Initalised")

    def image_callback(self, msg):
        self.get_logger().info("Recieved image")
        frame: np.ndarray = cv_bridge.imgmsg_to_cv2(msg)
        hsv_frame: np.ndarray = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        left_objects = get_coloured_objects(hsv_frame, [LEFT_THRESH])
        right_objects = get_coloured_objects(hsv_frame, [RIGHT_THRESH])

        # find "closest" (aka lowest) contours
        closest_left: Optional[Rect] = None
        closest_right: Optional[Rect] = None

        if len(left_objects) > 0:
            closest_left = max(left_objects, key=lambda r: r.bottom)
    
        if len(right_objects) > 0:
            closest_right = max(right_objects, key=lambda r: r.bottom)

        if closest_left is not None:
            draw_box(frame, box=closest_left, colour=LEFT_DISP_COLOUR)
        
        if closest_right is not None:
            draw_box(frame, box=closest_right, colour=RIGHT_DISP_COLOUR)

        cv2.imshow("frame", frame)
        cv2.waitKey(1)


def main(args=None):
    rclpy.init(args=args)

    controller_node = ControllerNode()

    rclpy.spin(controller_node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
