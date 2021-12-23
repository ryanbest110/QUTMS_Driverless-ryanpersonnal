# Import Custom Modules
from . import point_cloud_processing as pcp
from . import ground_plane_estimation as gpe
from . import line_extraction

# Import Python Modules
import time
import math
import numpy as np

# Import Logging
import logging
LOGGER = logging.getLogger(__name__)


def detect_cones(
        point_cloud: np.ndarray, 
        point_norms: np.ndarray, 
        print_logs: bool, 
        LIDAR_RANGE: int, 
        DELTA_ALPHA: float, 
        BIN_SIZE: float, 
        POINT_COUNT: int, 
        T_M: float, 
        T_M_SMALL: float, 
        T_B: float, 
        T_RMSE: float, 
        REGRESS_BETWEEN_BINS: bool, 
        stdout_handler,
    ) -> list:

    # Printing logs to terminal
    if print_logs:
        LOGGER.addHandler(stdout_handler)

    LOGGER.info("Hi from lidar_manager.")

    # Derived Constants
    SEGMENT_COUNT = math.ceil(2 * math.pi / DELTA_ALPHA)
    BIN_COUNT = math.ceil(LIDAR_RANGE / BIN_SIZE)

    # Discretise point cloud for real-time performance
    start_time = time.time()
    segments_bins_norms_z = pcp.get_discretised_positions(point_cloud, point_norms, DELTA_ALPHA, BIN_SIZE)
    end_time = time.time()

    LOGGER.info(f'Numpy PointCloud discretised in {end_time - start_time}s')

    # Calculate prototype point for every bin (if one exists)
    start_time = time.time()
    prototype_points = pcp.get_prototype_points(segments_bins_norms_z, SEGMENT_COUNT, BIN_COUNT)
    end_time = time.time()

    LOGGER.info(f'Prototype Points computed in {end_time - start_time}s')

    start_time = time.time()
    # ground_surface = gpe.get_ground_surface(prototype_points, SEGMENT_COUNT, BIN_COUNT, T_M, T_M_SMALL, T_B, T_RMSE, REGRESS_BETWEEN_BINS)
    
    # Old LiDAR 1.0 code
    ground_plane = line_extraction.get_ground_plane(prototype_points, SEGMENT_COUNT, BIN_COUNT)
    end_time = time.time()

    LOGGER.info(f'Ground Surface estimated in {end_time - start_time}s')

    return []
