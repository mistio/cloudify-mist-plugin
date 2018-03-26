FROM python:2.7-alpine

MAINTAINER mist.io <support@mist.io>

RUN apk add --update --no-cache \
    git \
    gcc \
    g++ \
    autoconf \
    libffi-dev \
    py-openssl \
    openssl-dev \
    py-cryptography

RUN pip install --no-cache cloudify==3.3

COPY ./plugin/mist.client/ /opt/cloudify-mist-plugin/plugin/mist.client/

RUN pip install -e /opt/cloudify-mist-plugin/plugin/mist.client/

RUN apk add --update --no-cache vim
RUN pip install ipython ipdb

COPY . /opt/cloudify-mist-plugin/

RUN pip install -e /opt/cloudify-mist-plugin/

RUN addgroup -S cloudify && adduser -S -G cloudify cloudify

RUN chmod 775 /usr/local/bin/cfy && \
    chmod 775 /opt/cloudify-mist-plugin/scripts/execute-workflow

USER cloudify

ENTRYPOINT ["/opt/cloudify-mist-plugin/scripts/execute-workflow"]

ENTRYPOINT ["/bin/sh"]
