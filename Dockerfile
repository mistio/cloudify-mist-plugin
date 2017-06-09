FROM python:2.7-alpine

MAINTAINER mist.io <support@mist.io>

RUN apk add --update --no-cache \
    git \
    gcc \
    g++ \
    autoconf \
    libffi-dev \
    py-openssl \
    python-dev \
    openssl-dev \
    py-virtualenv \
    py-cryptography

RUN virtualenv /home/cloudify/

WORKDIR /home/cloudify/

RUN ./bin/pip install --no-cache cloudify==3.3

RUN ln -s ./bin/cfy /usr/local/bin/

COPY ./plugin/mist.client/ /opt/cloudify-mist-plugin/plugin/mist.client/

RUN ./bin/pip install -e /opt/cloudify-mist-plugin/plugin/mist.client/

COPY . /opt/cloudify-mist-plugin/

RUN ./bin/pip install -e /opt/cloudify-mist-plugin/

RUN addgroup -S cloudify && adduser -S -G cloudify cloudify

RUN chmod 775 /usr/local/bin/cfy && \
    chmod 775 /opt/cloudify-mist-plugin/scripts/execute-workflow

ENTRYPOINT ["/opt/cloudify-mist-plugin/scripts/execute-workflow"]
