import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

# TODO Adapt your project configuration to your own project.
# The name of the package is the one to be used in runtime.
# The 'install_requires' is where you specify the package dependencies of your package. They will be automaticly installed, before your package.  # noqa: E501
setuptools.setup(
    name="backend",
    version="1.0.0-8",
    author="Backend team",
    author_email="backend@mov.ai",
    description="Dummy description",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MOV-AI/backend",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=["Programming Language :: Python :: 3"],
    install_requires=[
        "aiohttp==3.6.2", "aiohttp-cors==0.7.0", "pyjwt==1.7.1", "requests==2.22.0", "rospkg==1.3.0",
        "python-box==4.0.4", "deepdiff==5.8.0", "miracle-acl==0.0.4.post1", "PyYAML==5.1.2",
        "movai_core_shared", "gd_node" #,"dal"
    ],
    entry_points={},
)
