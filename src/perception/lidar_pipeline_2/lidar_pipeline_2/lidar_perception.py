# Import ROS2 Modules
import rclpy
from rclpy.node import Node

# Import ROS2 Message Modules
from sensor_msgs.msg import PointCloud2

# Import ROS2 Helper Modules
import ros2_numpy as rnp

# Import Custom Message Modules
from driverless_msgs.msg import ConeDetectionStamped

# Import Custom Modules
from .library import lidar_manager

# Import Helper Modules
import numpy as np

# Import Python Modules
import datetime
import pathlib
import os
import getopt
import sys
import time
import math

# Import Logging
import logging
LOGGER = logging.getLogger(__name__)


class ConeSensingNode(Node):
    def __init__(self, pc_node):
        super().__init__('cone_sensing')
        LOGGER.info('Initialising ConeSensingNode')

        self.pc_subscription = self.create_subscription(
            PointCloud2,
            pc_node,
            self.pc_callback,
            2)
        self.pc_subscription  # Prevent unused variable warning

        self.cone_publisher = self.create_publisher(
            ConeDetectionStamped,
            'cone_sensing/cones',
            5)

        self.count = 0

        LOGGER.info('Waiting for PointCloud2 data ...')

    def pc_callback(self, pc_msg):
        LOGGER.info('PointCloud2 message received')

        # Convert PointCloud2 message from LiDAR sensor to numpy array
        start_time = time.time()
        dtype_list = rnp.point_cloud2.fields_to_dtype(pc_msg.fields, pc_msg.point_step) # x y z intensity ring
        point_cloud = np.frombuffer(pc_msg.data, dtype_list)
        end_time = time.time()

        LOGGER.info(f'PointCloud2 converted to numpy array in {end_time - start_time}s')
        LOGGER.debug(point_cloud)

        # Globals to pass to lidar_manager
        global print_logs
        global stdout_handler
        global lidar_range
        global delta_alpha
        global bin_size

        # Calculating the normal of each point
        start_time = time.time()
        point_norms = np.linalg.norm([point_cloud['x'], point_cloud['y']], axis=0)

        # Creating mask to remove points outside of range
        mask = point_norms <= lidar_range

        # Applying mask
        point_norms = point_norms[mask]
        point_cloud = point_cloud[mask]
        end_time = time.time()

        LOGGER.info(f'Norm computed and out of bounds points removed in {end_time - start_time}s')

        # Number of points in point cloud
        POINT_COUNT = point_cloud.shape[0]
        LOGGER.info(f'POINT_COUNT = {POINT_COUNT}')

        # Identify cones within the received point cloud
        pc_cones = lidar_manager.detect_cones(point_cloud, point_norms, print_logs, lidar_range, delta_alpha, bin_size, POINT_COUNT, stdout_handler)

        self.count += 1

        # Publish identified cones
        cones_msg = ConeDetectionStamped(
            header=pc_msg.header,
            cones=pc_cones
        )

        self.cone_publisher.publish(cones_msg)

        total_time = time.time() - start_time
        LOGGER.info(f'Total Time: {total_time}s | Est. Hz: {1 / total_time}')


def main(args=sys.argv[1:]):
    # Defaults
    pc_node = '/velodyne_points'
    loglevel = 'info'

    global print_logs
    print_logs = False

    global lidar_range
    lidar_range = 20

    global delta_alpha
    delta_alpha = 2 * math.pi / 128  # Delta angle of segments

    global bin_size
    bin_size = 0.14  # Size of bins

    # Processing args
    opts, arg = getopt.getopt(args, str(), ['pc_node=', 'log=', 'lidar_range=', 'delta_alpha=', 'bin_size=', 'print_logs'])

    for opt, arg in opts:
        if opt == '--pc_node':
            pc_node = arg
        elif opt == '--log':
            loglevel = arg
        elif opt == '--lidar_range':
            lidar_range = arg
        elif opt == '--delta_alpha':
            delta_alpha = arg
        elif opt == '--bin_size':
            bin_size = arg
        elif opt == '--print_logs':
            print_logs = True

    # Validating args
    numeric_level = getattr(logging, loglevel.upper(), None)

    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)

    # Setting up logging
    path = str(pathlib.Path(__file__).parent.resolve())
    if not os.path.isdir(path + '/logs'):
        os.mkdir(path + '/logs')

    date = datetime.datetime.now().strftime('%d_%m_%Y_%H_%M_%S')
    logging.basicConfig(filename=f'{path}/logs/{date}.log',
                        filemode='w',
                        format='%(asctime)s | %(levelname)s:%(name)s: %(message)s',
                        datefmt='%I:%M:%S %p',
                        # encoding='utf-8',
                        level=numeric_level)

    # Printing logs to terminal
    if print_logs:
        global stdout_handler
        stdout_handler = logging.StreamHandler(sys.stdout)
        LOGGER.addHandler(stdout_handler)

    LOGGER.info('Hi from lidar_pipeline_2.')
    LOGGER.info(f'args = {args}')
    LOGGER.info(f'pc_node = {pc_node}')

    # Setting up node
    rclpy.init(args=args)

    cone_sensing_node = ConeSensingNode(pc_node)

    rclpy.spin(cone_sensing_node)

    # Destroy the node explicitly
    cone_sensing_node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main(sys.argv[1:])

# Notes
# 1. Intead of rounding the point cloud, see if setting the dtype to
#    16 bit float does the same thing / is faster. Rouding might still
#    leave the numbers as float32s
