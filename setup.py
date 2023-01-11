import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = [
    "aiohttp==3.8.1",
    "aiohttp-cors==0.7.0",
    "bleach==4.1.0",
    "ldap3==2.9.1",
    "miracle-acl==0.0.4.post1",
    "PyYAML==5.1.2",
    "requests==2.22.0",
    "gd_node==2.4.0.*",
]


setuptools.setup(
    name="backend",
    version="2.4.0-6",
    author="Backend team",
    author_email="backend@mov.ai",
    description="Movai Backend Package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MOV-AI/backend",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=["Programming Language :: Python :: 3"],
    install_requires=[requirements],
    entry_points={
        "console_scripts": [
            "backend = backend:main",
            "deploy_app = backend.tools.deploy_app:main",
            "gen_report = backend.tools.gen_report:main",
            "new_user = backend.tools.new_user:main",
            "user_tool = backend.tools.user_tool:main",
            "upload_ui = backend.tools.upload_ui:main",
        ]
    },
)
