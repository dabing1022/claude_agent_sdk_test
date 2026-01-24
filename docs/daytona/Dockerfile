FROM daytonaio/sandbox:0.4.3

USER root

ARG PYTHON_VERSION=3.14.2
ARG CLAUDE_AGENT_SDK_VERSION=0.1.21
ARG CLAUDE_CODE_VERSION=2.1.17

# Remove expired Yarn GPG key/source from base image
RUN rm -f /etc/apt/sources.list.d/yarn.list \
  && rm -f /usr/share/keyrings/yarn-keyring.gpg 2>/dev/null || true

# Build deps for Python from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev libffi-dev liblzma-dev tk-dev uuid-dev xz-utils \
  && rm -rf /var/lib/apt/lists/*

# Build and install latest Python
RUN curl -fsSLO https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz \
  && tar -xzf Python-${PYTHON_VERSION}.tgz \
  && cd Python-${PYTHON_VERSION} \
  && ./configure --prefix=/usr/local --enable-shared --with-ensurepip=install \
  && make -j"$(nproc)" \
  && make altinstall \
  && cd / \
  && rm -rf Python-${PYTHON_VERSION}*

RUN ldconfig

# Point python3/pip3 to the new version
RUN ln -sf /usr/local/bin/python3.14 /usr/local/bin/python3 \
  && ln -sf /usr/local/bin/pip3.14 /usr/local/bin/pip3

# Install Claude Agent SDK (latest)
RUN python3 -m pip install --upgrade pip --break-system-packages \
  && python3 -m pip install --no-cache-dir --break-system-packages claude-agent-sdk==${CLAUDE_AGENT_SDK_VERSION}

# Install Claude Code CLI (official recommended method)
RUN curl -fsSL https://claude.ai/install.sh | bash

USER daytona
ENTRYPOINT ["sleep", "infinity"]
