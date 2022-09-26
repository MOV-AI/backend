import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

# TODO Adapt your project configuration to your own project.
# The name of the package is the one to be used in runtime.
# The 'install_requires' is where you specify the package dependencies of your package. They will be automaticly installed, before your package.  # noqa: E501

requirements = [
    "bleach==4.1.0",
    "ldap3==2.9.1",
    "aiohttp==3.6.2",
    "aiohttp-cors==0.7.0",
    "requests==2.27.1",
    "deepdiff==4.0.9",
    "PyYAML==5.1.2",
    "rospkg==1.3.0",
    "dal==1.0.0.29",
    "gd_node==1.0.0.8"
]

setuptools.setup(
    name="backend",
    version="1.0.0-24",
    author="Backend team",
    author_email="backend@mov.ai",
    description="Dummy description",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MOV-AI/backend",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=["Programming Language :: Python :: 3"],
    install_requires=requirements,
    entry_points={},
)
