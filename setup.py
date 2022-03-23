import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

# TODO Adapt your project configuration to your own project.
# The name of the package is the one to be used in runtime.
# The 'install_requires' is where you specify the package dependencies of your package. They will be automaticly installed, before your package.  # noqa: E501
setuptools.setup(
    name="dummy-component",
    version="1.0.0-2",
    author="DevOps team",
    author_email="devops@mov.ai",
    description="Dummy description",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MOV-AI/repository-template-python-component",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=["Programming Language :: Python :: 3"],
    install_requires=[],
    entry_points={"console_scripts": ["my-command = DummyComponent.handler:handle"]},
)
