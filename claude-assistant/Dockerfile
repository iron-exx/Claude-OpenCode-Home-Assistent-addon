ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache jq

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

# s6-overlay v3 Service-Struktur (HA base images ab 2023)
RUN mkdir -p /etc/s6-overlay/s6-rc.d/claude/dependencies.d \
    && mkdir -p /etc/s6-overlay/s6-rc.d/user/contents.d \
    && echo "longrun" > /etc/s6-overlay/s6-rc.d/claude/type \
    && touch /etc/s6-overlay/s6-rc.d/claude/dependencies.d/base \
    && touch /etc/s6-overlay/s6-rc.d/user/contents.d/claude

COPY run.sh /etc/s6-overlay/s6-rc.d/claude/run
RUN chmod a+x /etc/s6-overlay/s6-rc.d/claude/run
