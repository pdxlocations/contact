FROM docker.io/python:3.14

COPY . /app
WORKDIR /data

# Install contact
RUN python -m pip install /app && rm -rf /app

VOLUME /data

ENTRYPOINT [ "contact" ]
