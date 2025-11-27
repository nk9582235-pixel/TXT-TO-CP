FROM ubuntu:latest
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends build-essential libffi-dev libssl-dev python3-dev python3-pip ffmpeg aria2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/
RUN pip3 install --no-cache-dir --upgrade --requirement Installer --break-system-packages
CMD python3 main.py
