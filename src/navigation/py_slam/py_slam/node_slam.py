from math import atan2, cos, hypot, pi, sin
import time

import numpy as np
from sklearn.neighbors import KDTree
from transforms3d.euler import quat2euler

import message_filters
import rclpy
from rclpy.node import Node
from rclpy.publisher import Publisher

from driverless_msgs.msg import Cone, ConeDetectionStamped, ConeWithCovariance, TrackDetectionStamped
from geometry_msgs.msg import Point, PoseWithCovarianceStamped

from driverless_common.cone_props import ConeProps

from typing import List, Tuple


def wrap_to_pi(angle: float) -> float:  # in rads
    return (angle + pi) % (2 * pi) - pi


def predict(pose_msg: PoseWithCovarianceStamped, R: np.ndarray, init_pose: list) -> Tuple[np.ndarray]:
    """Covariance from odom
    xx, xy, xz, xi, xj, xk
    yx, yy, yz, yi, yj, yk
    zx, zy, zz, zi, zj, zk
    ix, iy, iz, ii, ij, ik
    jx, jy, jz, ji, jj, jk
    kx, ky, kz, ki, kj, kk
    """

    # i, j, k angles in rad
    ai, aj, ak = quat2euler(
        [
            pose_msg.pose.pose.orientation.w,
            pose_msg.pose.pose.orientation.x,
            pose_msg.pose.pose.orientation.y,
            pose_msg.pose.pose.orientation.z,
        ]
    )

    x = pose_msg.pose.pose.position.x - init_pose[0]
    y = pose_msg.pose.pose.position.y - init_pose[1]
    theta = wrap_to_pi(ak - init_pose[2])

    muR = np.array([x, y, theta])  # robot mean

    cov = pose_msg.pose.covariance
    cov = np.reshape(cov, (6, 6))
    SigmaR = np.array(
        [[cov[0, 0], cov[0, 1], cov[0, 5]], [cov[1, 0], cov[1, 1], cov[1, 5]], [cov[5, 0], cov[5, 1], cov[5, 5]]]
    )

    return muR, SigmaR


def init_landmark(
    cone: Tuple[float, float], Q: np.ndarray, mu: np.ndarray, Sigma: np.ndarray  # (range,bearing)
) -> Tuple[np.ndarray, np.ndarray]:

    new_x = mu[0] + cone[0] * cos(mu[2] + cone[1])  # add local xy to robot xy
    new_y = mu[1] + cone[0] * sin(mu[2] + cone[1])
    mu = np.append(mu, [new_x, new_y])  # append new landmark

    # landmark Jacobian
    Lz = np.array(
        [
            [cos(mu[2] + cone[1]), cone[0] * -sin(mu[2] + cone[1])],
            [sin(mu[2] + cone[1]), cone[0] * cos(mu[2] + cone[1])],
        ]
    )

    sig_len = len(Sigma)
    new_sig = np.zeros((sig_len + 2, sig_len + 2))  # create zeros
    new_sig[0:sig_len, 0:sig_len] = Sigma  # top left corner is existing sigma
    new_sig[sig_len : sig_len + 2, sig_len : sig_len + 2] = Lz @ Q @ Lz.T  # bottom right is new lm

    return mu, new_sig  # new sigma overwrites sigma


def update(
    track: np.ndarray,
    index: int,
    cone: Tuple[float, float],  # (range,bearing)
    Q: np.ndarray,
    mu: np.ndarray,
    Sigma: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:

    i = index * 2 + 3  # landmark index, first 3 are robot, each landmark has 2 values
    muL = mu[i : i + 2]  # omit colour from location mean

    r = hypot(mu[0] - muL[0], mu[1] - muL[1])  # range to landmark
    b = wrap_to_pi(atan2(muL[1] - mu[1], muL[0] - mu[0]) - mu[2])  # bearing to lm
    h = [r, b]

    sig_len = len(Sigma)  # length of robot+landmarks we've seen so far

    G = np.zeros((2, sig_len))
    # robot jacobian
    GR = [
        [-(muL[0] - mu[0]) / r, -(muL[1] - mu[1]) / r, 0],
        [(muL[1] - mu[1]) / (r**2), -(muL[0] - mu[0]) / (r**2), 1],
    ]
    # landmark jacobian
    GL = [[(muL[0] - mu[0]) / r, (muL[1] - mu[1]) / r], [-(muL[1] - mu[1]) / (r**2), (muL[0] - mu[0]) / (r**2)]]

    G[0:2, 0:3] = GR  # first 2 rows, 3 columns
    G[0:2, i : i + 2] = GL  # index columns, 2 rows

    K = Sigma @ G.T @ np.linalg.inv(G @ Sigma @ G.T + Q)
    z_h = np.reshape([cone[0] - h[0], cone[1] - h[1]], (-1, 1))  # turn into a 2D column array

    addon = (K @ z_h).T
    mu = mu + addon[0]  # because this was 2D... had to take 'first' element
    Sigma = (np.eye(sig_len) - K @ G) @ Sigma

    track[index, :2] = mu[i : i + 2]  # track for this cone is just cone's mu

    track[index, 3] += 1  # increment cone's seen count

    return mu, Sigma, track


class EKFSlam(Node):
    R = np.diag([0.05, 0.05, 0.05])  # very confident of odom (cause its OP)
    Q = np.diag([1, 0.8]) ** 2  # detections are a bit meh
    radius = 2  # nn kdtree nearch
    leaf = 50  # nodes per tree before it starts brute forcing?
    in_frames = 7  # minimum frames that cones have to be seen in
    mu = np.array([3.0, 0.0, 0.0])  # initial pose
    Sigma: np.ndarray = np.diag([0.01, 0.01, 0.01])
    track: np.ndarray = []

    # init pose on first odom message
    init_pose: list = [0.0, 0.0, 0.0]
    pose_zeroed = True  # cant get zeroing to work, skipping for now

    def __init__(self):
        super().__init__("ekf_slam")

        # sync subscribers
        pose_sub = message_filters.Subscriber(self, PoseWithCovarianceStamped, "/zed2i/zed_node/pose_with_covariance")
        vision_sub = message_filters.Subscriber(self, ConeDetectionStamped, "/vision/cone_detection")
        lidar_sub = message_filters.Subscriber(self, ConeDetectionStamped, "/lidar/cone_detection")
        vision_synchronizer = message_filters.ApproximateTimeSynchronizer(
            fs=[pose_sub, vision_sub], queue_size=20, slop=0.2
        )
        vision_synchronizer.registerCallback(self.callback)
        lidar_synchronizer = message_filters.ApproximateTimeSynchronizer(
            fs=[pose_sub, lidar_sub], queue_size=20, slop=0.2
        )
        lidar_synchronizer.registerCallback(self.callback)

        # slam publisher
        self.slam_publisher: Publisher = self.create_publisher(TrackDetectionStamped, "/slam/track", 1)
        self.local_publisher: Publisher = self.create_publisher(TrackDetectionStamped, "/slam/local", 1)

        self.get_logger().info("---SLAM node initialised---")

    # remove landmarks we haven't seen in a while
    def flush_map(self):
        # only remove landmarks if they are behind us

        # get the robot's heading vector
        heading = np.array([cos(self.mu[2]), sin(self.mu[2])])
        # get the robot's position vector
        position = np.array([self.mu[0], self.mu[1]])

        # get the landmark position vectors
        # if the landmark is behind the robot, the dot product will be negative
        landmark_position_vectors = self.track[:, :2] - position
        # get the dot product of the landmark position vector and the robot heading vector
        dot_products = np.dot(landmark_position_vectors, heading)
        # get the indexes of the landmarks that are behind the robot
        behind_idxs = np.where(dot_products < 0)[0]

        # get indexes of landmarks we haven't seen in a while
        noisy_idxs = np.where(self.track[:, 3] < self.in_frames)[0]

        # remove noisy and behind landmarks
        idxs_to_remove = np.concatenate((behind_idxs, noisy_idxs))  # gets any indexes behind and noisy
        unique, count = np.unique(idxs_to_remove, return_counts=True)  # gets unique indexes
        duplicated_idxs = unique[count > 1]  # only gets indexes that are duplicated (behind and noisy)

        if len(duplicated_idxs) > 0:
            # remove landmarks from mu and Sigma
            self.mu = np.delete(self.mu, [duplicated_idxs * 2 + 3, duplicated_idxs * 2 + 4], axis=0)

            # remove landmarks from Sigma
            self.Sigma = np.delete(self.Sigma, [duplicated_idxs * 2 + 3, duplicated_idxs * 2 + 4], axis=0)  # rows
            self.Sigma = np.delete(self.Sigma, [duplicated_idxs * 2 + 3, duplicated_idxs * 2 + 4], axis=1)  # columns

            # remove landmarks from track
            self.track = np.delete(self.track, duplicated_idxs, axis=0)

    # get cones within view of the cars
    def get_local_map(self) -> np.ndarray:
        # global to local
        local_xs = (self.track[:, 0] - self.mu[0]) * cos(self.mu[2]) + (self.track[:, 1] - self.mu[1]) * sin(self.mu[2])
        local_ys = -(self.track[:, 0] - self.mu[0]) * sin(self.mu[2]) + (self.track[:, 1] - self.mu[1]) * cos(
            self.mu[2]
        )

        local_track = np.stack((local_xs, local_ys, self.track[:, 2], self.track[:, 3]), axis=1)

        # get any cones that are within -10m to 10m beside cars
        side_idxs = np.where(np.logical_and(local_ys > -10, local_ys < 10))[0]
        # get any cones that are within 10m in front of cars
        forward_idxs = np.where(np.logical_and(local_xs > 0, local_xs < 10))[0]

        # combine indexes
        idxs = np.intersect1d(side_idxs, forward_idxs)

        # get local map
        return local_track[idxs]

    def callback(self, pose_msg: PoseWithCovarianceStamped, detection_msg: ConeDetectionStamped):
        self.get_logger().debug("Received detection")
        start: float = time.perf_counter()

        # check if zeroed pose - on first detection
        if not self.pose_zeroed:
            init_x = pose_msg.pose.pose.position.x
            init_y = pose_msg.pose.pose.position.y
            _, _, init_theta = quat2euler(
                [
                    pose_msg.pose.pose.orientation.w,
                    pose_msg.pose.pose.orientation.x,
                    pose_msg.pose.pose.orientation.y,
                    pose_msg.pose.pose.orientation.z,
                ]
            )
            self.init_pose = [init_x, init_y, init_theta]
            self.pose_zeroed = True

        # predict car location (pretty accurate odom)
        muR, SigmaR = predict(pose_msg, self.R, self.init_pose)
        self.mu[0:3] = muR
        self.Sigma[0:3, 0:3] = SigmaR

        # process detected cones
        for cone in detection_msg.cones:
            det = ConeProps(cone)  # detection with properties

            mapx = self.mu[0] + det.range * cos(self.mu[2] + det.bearing)
            mapy = self.mu[1] + det.range * sin(self.mu[2] + det.bearing)

            on_map = False  # by default its a new detection

            if len(self.track) != 0:
                neighbourhood = KDTree(self.track[:, :2], leaf_size=self.leaf)
                check = np.reshape([mapx, mapy], (1, -1))  # turn into a 2D row array
                ind = neighbourhood.query_radius(check, r=self.radius)  # check neighbours in radius
                close = ind[0]  # index from the single colour list
                if close.size != 0:
                    on_map = True
                    self.mu, self.Sigma, self.track = update(
                        self.track, close[0], det.sense_rb, self.Q, self.mu, self.Sigma
                    )
                    if det.colour != Cone.UNKNOWN:  # updated cone was not a lidar detection
                        self.track[close[0]][2] = det.colour  # override colour

            if not on_map:
                if self.track == []:  # first in this list
                    self.track = np.array([mapx, mapy, det.colour, 1])
                    self.track = np.reshape(self.track, (1, -1))  # turn 2D
                else:  # otherwise append vertically
                    self.track = np.vstack([self.track, [mapx, mapy, det.colour, 1]])
                # initialise new landmark
                self.mu, self.Sigma = init_landmark(det.sense_rb, self.Q, self.mu, self.Sigma)

        # remove noise
        self.flush_map()

        # get local map
        local_map = self.get_local_map()

        # publish track msg
        track_msg = TrackDetectionStamped()
        track_msg.header.stamp = pose_msg.header.stamp
        track_msg.header.frame_id = "map"
        for i, cone in enumerate(self.track):
            cov_i = i * 2 + 3
            curr_cov: np.ndarray = self.Sigma[cov_i : cov_i + 2, cov_i : cov_i + 2]  # 2x2 covariance to plot
            cone_msg = Cone(location=Point(x=cone[0], y=cone[1], z=0.0), color=int(cone[2]))
            cone_cov = curr_cov.flatten().tolist()
            track_msg.cones.append(ConeWithCovariance(cone=cone_msg, covariance=cone_cov))
        self.slam_publisher.publish(track_msg)

        # publish local map msg
        local_map_msg = TrackDetectionStamped()
        local_map_msg.header.stamp = pose_msg.header.stamp
        local_map_msg.header.frame_id = "base_link"
        for i, cone in enumerate(local_map):
            cov_i = i * 2 + 3
            curr_cov: np.ndarray = self.Sigma[cov_i : cov_i + 2, cov_i : cov_i + 2]
            cone_msg = Cone(location=Point(x=cone[0], y=cone[1], z=0.0), color=int(cone[2]))
            cone_cov = curr_cov.flatten().tolist()
            local_map_msg.cones.append(ConeWithCovariance(cone=cone_msg, covariance=cone_cov))
        self.local_publisher.publish(local_map_msg)

        # self.get_logger().info(f"Wait time: {str(time.perf_counter()-start)}")  # log time


def main(args=None):
    rclpy.init(args=args)
    node = EKFSlam()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
