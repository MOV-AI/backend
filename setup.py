import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = []

with open("requirements.txt", "r") as fh:
    for line in fh.readlines(): 
        if line != '\n':
            if '\n' in line:
                line = line.rstrip('\n')
            requirements.append(str(line))


setuptools.setup(
    name="backend",
    version="1.0.1-0",
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
        "console_scripts":[
            "backend = backend:main",
            "deploy_app = backend.tools.deploy_app:main",
            "gen_report = backend.tools.gen_report:main",
            "new_user = backend.tools.new_user:main",
            "user_tool = backend.tools.user_tool:main",
            "upload_ui = backend.tools.upload_ui:main"
        ]
        },
)
