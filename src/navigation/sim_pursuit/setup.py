from setuptools import setup

package_name = "sim_pursuit"

setup(
    name=package_name,
    version="0.0.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Alastair Bradford",
    maintainer_email="team@qutmotorsport.com",
    description="Plans a target path and waypoint to approach",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "local_pursuit = sim_pursuit.node_local_pursuit:main",
        ],
    },
)