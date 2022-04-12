ARG DOCKER_REGISTRY="registry.cloud.mov.ai"
FROM ${DOCKER_REGISTRY}/devops/movai-base-melodic:v1.4.5

# Arguments
ARG PIP_PACKAGE_REPO="https://artifacts.cloud.mov.ai/repository/pypi-experimental/simple"
ARG PIP_PACKAGE_NAME="backend"
ARG PIP_PACKAGE_VERSION="1.0.0.2"

# Labels
LABEL description="MOV.AI Backend Image"
LABEL maintainer="devops@mov.ai"
LABEL movai="backend"
LABEL environment="release"

### Environment config
ENV MOVAI_ENV="release" \
    REDIS_MASTER_HOST="redis-master" \
    REDIS_MASTER_PORT=6379 \
    REDIS_LOCAL_HOST="redis-local" \
    REDIS_LOCAL_PORT=6379 \
    APP_NAME="backend" \
    MOVAI_MANAGER_URI="http://localhost:5004" \
    FLEET_TOKEN=""

# Copy packages definition and run install script
COPY docker/files/packages.apt /tmp/packages.apt
RUN /usr/local/bin/install-packages.sh

# Specific tasks to do to the user homespace
COPY docker/files/user.rc /tmp/user.rc
RUN /usr/local/bin/user-provision.sh

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install PIP package
RUN pip install --no-cache-dir \
    --index-url="$PIP_PACKAGE_REPO" \
    --extra-index-url https://pypi.org/simple \
    "$PIP_PACKAGE_NAME==$PIP_PACKAGE_VERSION"

# Copy runtime scripts
COPY docker/files/install-package.sh /usr/local/bin/install-package.sh
COPY docker/files/create-user.sh /usr/local/bin/create-user.sh

# Copy entrypoint script
COPY docker/files/movai-entrypoint.sh /usr/local/bin/movai-entrypoint.sh

# Run everything as mov.ai user
USER movai
