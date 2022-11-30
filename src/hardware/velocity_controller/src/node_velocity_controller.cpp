#include <iostream>

#include "ackermann_msgs/msg/ackermann_drive_stamped.hpp"
#include "driverless_msgs/msg/motor_rpm.hpp"
#include "rclcpp/rclcpp.hpp"

using std::placeholders::_1;

class Velocity_Controller : public rclcpp::Node {
   private:
    float Kp_vel = 0;
    float Ki_vel = 0;
    float Kd_vel = 0;

    float integral_error = 0;
    float prev_error = 0;

    rclcpp::Publisher<ackermann_msgs::msg::AckermannDriveStamped>::SharedPtr accel_pub;
    rclcpp::Subscription<ackermann_msgs::msg::AckermannDriveStamped>::SharedPtr ackermann_sub;
    rclcpp::Subscription<driverless_msgs::msg::MotorRPM>::SharedPtr motorRPM_sub;

    ackermann_msgs::msg::AckermannDriveStamped target_ackermann;
    // velocity of each wheel in m/s
    float motor_velocities[4];

    const int MOTOR_COUNT = 4;
    const float WHEEL_RADIUS = 0.4064;

    rclcpp::TimerBase::SharedPtr controller_timer;

    rclcpp::Time _internal_status_time;

    void ackermann_callback(const ackermann_msgs::msg::AckermannDriveStamped msg) { this->target_ackermann = msg; }

    void rpm_callback(const driverless_msgs::msg::MotorRPM msg) {
        if (msg.index < MOTOR_COUNT) {
            // valid wheel, so convert from rpm to m/s

            // convert from eRPM
            float motorRPM = msg.rpm / (21.0 * 4.50);

            // convert to m/s
            motor_velocities[msg.index] = motorRPM * M_PI * this->WHEEL_RADIUS / 60;
        }
    }

    void controller_callback() {
        // PID controller for velocity here

        // average all 4 motor velocities to use as 'current'
        float av_velocity = 0;

        for (int i = 0; i < MOTOR_COUNT; i++) {
            av_velocity += this->motor_velocities[i];
        }

        av_velocity = av_velocity / MOTOR_COUNT;

        // calculate error
        float error = this->target_ackermann.drive.speed - av_velocity;

        this->integral_error += error;

        float derivative_error = error - this->prev_error;

        // calculate control variable
        float accel = (this->Kp_vel * error) + (this->Ki_vel * integral_error) + (this->Kd_vel * derivative_error);
        
        RCLCPP_INFO(this->get_logger(), "Kp: %f err: %f Ki: %f i: %f Kd: %f d: %f accel: %f", Kp_vel, error, Ki_vel,
                    integral_error, Kd_vel, derivative_error, accel);

        this->prev_error = error;

        // limit output accel to be between -1 (braking) and 1 (accel)
        if (accel > 1) {
            accel = 1;
        } else if (accel < -1) {
            accel = -1;
        }

        // create control ackermann based off desired and calculated acceleration
        ackermann_msgs::msg::AckermannDriveStamped accel_cmd;
        accel_cmd.header.stamp = this->now();
        accel_cmd.drive = this->target_ackermann.drive;
        accel_cmd.drive.acceleration = accel;

        // publish accel
        this->accel_pub->publish(accel_cmd);
    }

   public:
    Velocity_Controller() : Node("velocity_controller") {
        // PID controller parameters
        this->declare_parameter<float>("Kp_vel", 0);
        this->declare_parameter<float>("Ki_vel", 0);
        this->declare_parameter<float>("Kd_vel", 0);

        this->get_parameter("Kp_vel", this->Kp_vel);
        this->get_parameter("Ki_vel", this->Ki_vel);
        this->get_parameter("Kd_vel", this->Kd_vel);

        // Configure logger level
        this->get_logger().set_level(rclcpp::Logger::Level::Debug);

        // Ackermann
        this->ackermann_sub = this->create_subscription<ackermann_msgs::msg::AckermannDriveStamped>(
            "/driving_command", 10, std::bind(&Velocity_Controller::ackermann_callback, this, _1));

        // Velocity updates
        this->motorRPM_sub = this->create_subscription<driverless_msgs::msg::MotorRPM>(
            "/motor_rpm", 10, std::bind(&Velocity_Controller::rpm_callback, this, _1));

        // Control loop -> 10ms so runs at double speed heartbeats are sent at
        this->controller_timer = this->create_wall_timer(std::chrono::milliseconds(10),
                                                         std::bind(&Velocity_Controller::controller_callback, this));

        // Acceleration command publisher
        this->accel_pub = this->create_publisher<ackermann_msgs::msg::AckermannDriveStamped>("accel_command", 10);

        // PID parameters
        RCLCPP_INFO(this->get_logger(), "PID parameters: Kp %f Kf %f Kd %f", this->Kp_vel, this->Ki_vel, this->Kd_vel);
    }
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<Velocity_Controller>());
    rclcpp::shutdown();
    return 0;
}
