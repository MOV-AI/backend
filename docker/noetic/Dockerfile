ARG DOCKER_REGISTRY="pubregistry.aws.cloud.mov.ai"
FROM ${DOCKER_REGISTRY}/ce/movai-base-focal:v2.4.0

# Arguments
ARG PIP_PACKAGE_REPO="https://artifacts.cloud.mov.ai/repository/pypi-experimental/simple"

# Labels
LABEL description="MOV.AI Backend Image"
LABEL maintainer="devops@mov.ai"
LABEL movai="backend"
LABEL environment="release"

### Environment config
ENV MOVAI_ENV="release" \
    HTTP_PORT=5004 \
    REDIS_MASTER_HOST="redis-master" \
    REDIS_MASTER_PORT=6379 \
    REDIS_LOCAL_HOST="redis-local" \
    REDIS_LOCAL_PORT=6379 \
    APP_NAME="backend" \
    MOVAI_MANAGER_URI="http://localhost:5004" \
    FLEET_TOKEN="" \
    PYTHON_VERSION=3.8

# Copy packages definition and run install script
COPY docker/files/packages.apt /tmp/packages.apt
RUN /usr/local/bin/install-packages.sh

# Specific tasks to do to the user homespace
COPY docker/files/user.rc /tmp/user.rc
RUN /usr/local/bin/user-provision.sh

COPY dist /tmp/dist
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install PIP package
RUN python3 -m pip install --no-cache-dir \
    --index-url="$PIP_PACKAGE_REPO" \
    --extra-index-url https://pypi.org/simple \
    /tmp/dist/*.whl && \
    mkdir -p /opt/mov.ai/app/tools && \
    rm -rf /tmp/dist && \
    cp /usr/local/lib/python${PYTHON_VERSION}/dist-packages/backend/tools/*.py /opt/mov.ai/app/tools/ && \
    cp -f /usr/local/lib/python${PYTHON_VERSION}/dist-packages/dal/tools/*.py /opt/mov.ai/app/tools/ && \
    cp -f /usr/local/lib/python${PYTHON_VERSION}/dist-packages/backend/tools/deploy_app.py /opt/mov.ai/app/tools/deployApp.py

# Copy runtime scripts
COPY docker/files/install-package.sh /usr/local/bin/install-package.sh
COPY docker/files/create-user.sh /usr/local/bin/create-user.sh

# Copy entrypoint script
COPY docker/files/movai-entrypoint.sh /usr/local/bin/movai-entrypoint.sh

# Run everything as mov.ai user
USER movai

HEALTHCHECK CMD echo > /dev/tcp/localhost/${HTTP_PORT} || exit 1
