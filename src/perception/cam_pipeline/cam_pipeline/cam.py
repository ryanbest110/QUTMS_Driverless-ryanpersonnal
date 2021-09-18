# import ROS2 libraries
import rclpy
from rclpy.node import Node
from cv_bridge import CvBridge # package to convert between ROS and OpenCV Images
# import ROS2 message libraries
from sensor_msgs.msg import Image
# importcustom sim data message libraries
from qutms_msgs.msg import ConeScan, ConeData

# import other python libraries
import numpy as np
import cv2
import time

# import helper image processing module
from .sub_module.img_processing import *
# import helper cone location processing module
from .sub_module.loc_processing import *


class CamDetection(Node):
    def __init__(self):
        super().__init__('control')

         # creates subscriber to 'cam1' with type Image that sends data to cam_callback
        self.cam_subscription_ = self.create_subscription(
            Image,
            '/fsds/camera/cam1',
            self.cam_callback,
            10)
        self.cam_subscription_  # prevent unused variable warning
        self.br = CvBridge()
        self.cone_coords = list()
        self.n = 0
        self.start = time.time()

        ## creates publisher to 'control_command' with type ControlCommand
        # self.scan_publisher_ = self.create_publisher(
        #     ConeScan,
        #     'lidar_output', 
        #     10)
        # # creates timer for publishing commands
        # self.timer_period = 0.001  # seconds
        # self.timer = self.create_timer(self.timer_period, self.publisher)


    # callback function for camera image processing
    def cam_callback(self, cam_msg):
        # get image
        raw_frame = self.br.imgmsg_to_cv2(cam_msg)
        h, w, _ = raw_frame.shape

        display = True
        cones = cam_main(raw_frame, display)

        # call display_locations to return xyzc for every cone
        self.cone_coords = display_locations(w/2, cones) # send cones for distance calculation

        print("\n cone_coords: ", self.cone_coords)

        # self.n += 1
        # if self.n == 100:
        #     print(time.time() - self.start)

    # def publisher(self):
    #     cone_scan = ConeScan()
    #     # head = Header()

    #     cone_data = list()
    #     for i in range(len(self.cones)):
    #         cone = ConeData()
    #         cone.x = self.cones[i][0]
    #         cone.y = self.cones[i][1]
    #         cone.z = self.cones[i][2]
    #         cone.c = self.cones[i][3]
    #         cone_data.append(cone)
       
    #     # cant work out how headers work lmao, this breaks stuff
    #     # head.stamp = rospy.Time.now()
    #     # head.frame_id = "lidar2"
    #     # cone_scan.header = head

    #     cone_scan.data = cone_data

    #     self.scan_publisher_.publish(cone_scan)


## main call
def main(args=None):
    rclpy.init(args=args)

    node = CamDetection()
    rclpy.spin(node)
    
    node.destroy_node()

    rclpy.shutdown()


if __name__ == '__main__':
    main()
