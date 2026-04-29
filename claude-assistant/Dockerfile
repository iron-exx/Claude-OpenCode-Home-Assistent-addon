ARG BUILD_FROM
FROM ${BUILD_FROM}

# jq für Config-Lesen
RUN apk add --no-cache jq

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

# s6-Service anlegen – HA Base Images nutzen s6-overlay als Init
RUN mkdir -p /etc/services.d/claude
COPY run.sh /etc/services.d/claude/run
RUN chmod a+x /etc/services.d/claude/run
