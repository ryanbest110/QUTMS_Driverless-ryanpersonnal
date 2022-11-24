import matplotlib.pyplot as plt
import numpy as np

from . import ground_plane_estimator as gpe
from . import object_processor as op
from . import point_classifier as pc
from . import point_cloud_processor as pcp
from . import visualiser as vis
from .. import constants as const
from ..utils import Config  # For typing


def locate_cones(config, point_cloud):
    config.logger.info(f"Point Cloud received with {point_cloud.shape[0]} points")

    # Visualise inital point cloud before filtering
    if config.create_figures:
        config.setup_image_dir()
        # vis.plot_point_cloud_2D(config, point_cloud, "00_PointCloud_2D")

    # Remove points behind car
    point_cloud = point_cloud[point_cloud["x"] > 0]

    # Compute point normals
    point_norms = np.linalg.norm([point_cloud["x"], point_cloud["y"]], axis=0)

    # Remove points that are outside of range or have a norm of 0
    mask = point_norms <= const.LIDAR_RANGE  # & (point_norms != 0)
    point_norms = point_norms[mask]
    point_cloud = point_cloud[mask]
    config.logger.info(f"{point_cloud.shape[0]} points remain after filtering point cloud")

    segments, bins = pcp.get_discretised_positions(point_cloud["x"], point_cloud["y"], point_norms)
    config.logger.info(f"DONE: Segments and Bins")

    proto_segs_arr, proto_segs, seg_bin_z_ind = pcp.get_prototype_points(point_cloud["z"], segments, bins, point_norms)
    config.logger.info(f"DONE: Prototype Points")

    # Multiprocessing Ground Plane Mapping [m b start(x, y) end(x, y) bin]
    # ground_plane = gpe.get_ground_plane_mp(config, proto_segs_arr, proto_segs)
    ground_plane = gpe.get_ground_plane_single_core(proto_segs_arr, proto_segs)
    config.logger.info(f"DONE: Ground Plane Mapped")

    # point_labels = pc.label_points(point_cloud, point_norms, seg_bin_z_ind, segments, ground_plane, bins)
    # point_labels = pc.label_points_2(point_cloud, point_norms, segments, bins, seg_bin_z_ind, ground_plane)
    # point_labels = pc.label_points_3(point_cloud, segments, bins, seg_bin_z_ind, ground_plane)
    # point_labels = pc.label_points_4(point_cloud, segments, bins, proto_segs, seg_bin_z_ind, ground_plane)
    # point_labels = pc.label_points_5(point_cloud, segments, bins, seg_bin_z_ind, ground_plane)
    point_labels, ground_lines_arr = pc.label_points_6(point_cloud["z"], segments, bins, seg_bin_z_ind, ground_plane)
    config.logger.info(f"DONE: Points Labelled")

    object_points = point_cloud[point_labels]
    config.logger.info("DONE: Object Points Grouped")

    if object_points.size == 0:
        config.logger.info("No objects points detected")
        return None

    object_centers, objects = op.group_points(object_points)  # maybe improve speed?
    config.logger.info(f"DONE: Objects Identified")

    # reconstructed_objects = op.reconstruct_objects(point_cloud, object_centers, objects, const.DELTA_ALPHA, const.CONE_DIAM, const.BIN_SIZE)
    reconstructed_objects = op.reconstruct_objects_2(point_cloud, segments, bins, object_centers, objects)

    # Investigate turning structured arrays into normal arrays for better indexing and avoiding column stack

    # Create visualisations
    if config.create_figures:
        # vis.plot_point_cloud_2D(config, point_cloud, "01_PointCloud_2D")
        # vis.plot_segments_2D(config, point_cloud, segments, "03_PointCloudSegments_2D")
        # vis.plot_bins_2D(config, point_cloud, bins, "05_PointCloudBins_2D")
        # vis.plot_segments_3D(config, point_cloud, segments, "04_PointCloudSegments_3D")
        # vis.plot_bins_3D(config, point_cloud, bins, "06_PointCloudBins_3D")
        # vis.plot_prototype_points_2D(config, proto_segs_arr, proto_segs, "07_PrototypePoints_2D")
        # vis.plot_prototype_points_3D(config, proto_segs_arr, proto_segs, "08_PrototypePoints_3D")
        # vis.plot_ground_plane_2D(config, ground_plane, proto_segs_arr, proto_segs, "09_GroundPlane_2D")
        # vis.plot_ground_plane_3D(config, ground_plane, proto_segs_arr, proto_segs, "10_GroundPlane_3D")
        # vis.plot_labelled_points_2D(config, point_cloud, point_labels, ground_plane, "11_LabelledPoints_2D")
        # vis.plot_labelled_points_3D(
        #    config, point_cloud, point_labels, ground_plane, "12_LabelledPoints_3D"
        # )
        vis.plot_object_points_2D(config, object_points, "13_Object_Points_2D")
        vis.plot_object_centers_2D(config, object_points, object_centers, "14_Objects_2D")
        # vis.plot_reconstructed_objects_2D(config, reconstructed_objects, "14_Reconstructed_Objects")

        if config.show_figures:
            plt.show()
