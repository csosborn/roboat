# Use an official lightweight Linux distribution as a base
FROM debian:bullseye-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install required packages
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3 \
    python3-pip \
    python3-venv \
    libffi-dev \
    libssl-dev \
    gcc-arm-none-eabi \
    binutils-arm-none-eabi \
    cmake \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /workspace
WORKDIR /workspace

# Create a user to avoid running as root
RUN useradd -m -s /bin/bash micropython
RUN chown -R micropython /workspace

USER micropython


# Clone the ulab repository
RUN git clone --depth=1 https://github.com/v923z/micropython-ulab ulab

# Clone the MicroPython repository
RUN git clone --depth=1 https://github.com/micropython/micropython.git micropython
RUN cd /workspace/micropython && git submodule update --init lib/tinyusb && git submodule update --init lib/pico-sdk
RUN cd /workspace/micropython/lib/pico-sdk && git submodule update --init lib/tinyusb

# Build mpy-cross as per MicroPython instructions
RUN cd /workspace/micropython/mpy-cross && make

# Build rp2 submodules
RUN cd /workspace/micropython/ports/rp2 && make submodules

# Add an entrypoint script to automate the build process
COPY --chown=micropython:micropython entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Volumes:
# - Source code should be mounted at /src
# - Build artifacts should be stored in a volume mounted at /build
