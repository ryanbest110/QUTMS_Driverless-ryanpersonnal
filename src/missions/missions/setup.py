from glob import glob
import os

from setuptools import setup

package_name = "missions"

setup(
    name=package_name,
    version="0.0.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Alastair Bradford",
    maintainer_email="team@qutmotorsport.com",
    description="Each driving event mission code",
    license="MIT",
    tests_require=["pytest"],
)