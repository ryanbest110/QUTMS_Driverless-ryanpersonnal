# Import ROS2 Modules
import rclpy
from rclpy.node import Node
# Import ROS2 Message Modules
from sensor_msgs.msg import PointCloud2
# Import Custom Message Modules
from driverless_msgs.msg import ConeDetectionStamped
# Import ROS2 Helper Modules
import ros2_numpy as rnp

# Import Custom Modules
from .library import lidar_manager

# Import Python Modules
import numpy as np
import datetime
import pathlib
import os
import getopt
import sys
import time
import math
from typing import List

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
        dtype_list: List = rnp.point_cloud2.fields_to_dtype(pc_msg.fields, pc_msg.point_step) # x y z intensity ring
        point_cloud: np.ndarray = np.frombuffer(pc_msg.data, dtype_list)
        end_time = time.time()

        LOGGER.info(f'PointCloud2 converted to numpy array in {end_time - start_time}s')
        LOGGER.debug(point_cloud)

        # Globals to pass to lidar_manager
        global print_logs
        global stdout_handler

        # these can all be self. variables if passed into the node init()
        # then referenced in here
        global LIDAR_RANGE
        global DELTA_ALPHA
        global BIN_SIZE

        global T_M
        global T_M_SMALL
        global T_B
        global T_RMSE
        global REGRESS_BETWEEN_BINS

        # Calculating the normal of each point
        start_time = time.time()
        point_norms: np.ndarray = np.linalg.norm([point_cloud['x'], point_cloud['y']], axis=0)

        # Creating mask to remove points outside of range
        mask: np.ndarray = point_norms <= LIDAR_RANGE

        # Applying mask
        point_norms = point_norms[mask]
        point_cloud = point_cloud[mask]
        end_time = time.time()

        LOGGER.info(f'Norm computed and out of range points removed in {end_time - start_time}s')

        # Number of points in point cloud
        point_count: int = point_cloud.shape[0]
        LOGGER.info(f'POINT_COUNT = {point_count}')

        # Identify cones within the received point cloud
        pc_cones: list = lidar_manager.detect_cones(point_cloud, point_norms, print_logs, LIDAR_RANGE, DELTA_ALPHA, BIN_SIZE, POINT_COUNT, T_M, T_M_SMALL, T_B, T_RMSE, REGRESS_BETWEEN_BINS, stdout_handler)

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

    # Max range of points to process (metres)
    global LIDAR_RANGE
    LIDAR_RANGE = 5

    # Delta angle of segments
    global DELTA_ALPHA
    DELTA_ALPHA = (2 * math.pi) / 128

    # Size of bins
    global BIN_SIZE
    BIN_SIZE = 0.14

    # Max angle that will be considered for ground lines
    global T_M
    T_M = (2 * math.pi) / 152

    # Angle considered to be a small slope
    global T_M_SMALL
    T_M_SMALL = 0

    # Max y-intercept for a ground plane line
    global T_B
    T_B = 0.1

    # Threshold of the Root Mean Square Error of the fit (Recommended: 0.2 - 0.5)
    global T_RMSE
    T_RMSE = 0.2

    # Determines if regression for ground lines should occur between two
    # neighbouring bins when they're described by different lines
    global REGRESS_BETWEEN_BINS
    REGRESS_BETWEEN_BINS = True

    # Processing args
    opts, arg = getopt.getopt(args, str(), ['pc_node=',
                                            'log=',
                                            'lidar_range=',
                                            'delta_alpha=',
                                            'bin_size=',
                                            't_m=',
                                            't_m_small=',
                                            't_b=',
                                            't_rmse=',
                                            'no_regress',
                                            'print_logs'])

    for opt, arg in opts:
        if opt == '--pc_node':
            pc_node = arg
        elif opt == '--log':
            loglevel = arg
        elif opt == '--lidar_range':
            LIDAR_RANGE = arg
        elif opt == '--delta_alpha':
            DELTA_ALPHA = arg
        elif opt == '--bin_size':
            BIN_SIZE = arg
        elif opt == '--t_m':
            T_M = arg
        elif opt == '--t_m_small':
            T_M_SMALL = arg
        elif opt == '--t_b':
            T_B = arg
        elif opt == '--t_rmse':
            T_RMSE = arg
        elif opt == '--no_regress':
            REGRESS_BETWEEN_BINS = False
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
