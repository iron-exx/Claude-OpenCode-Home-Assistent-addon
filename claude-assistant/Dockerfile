ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache jq

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# run.sh direkt als PID 1 – kein s6-overlay
ENTRYPOINT ["/run.sh"]
