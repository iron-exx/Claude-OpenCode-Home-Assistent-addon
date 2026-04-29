ARG BUILD_FROM
FROM ${BUILD_FROM}

# jq für Config-Parsing, curl für Health-Checks
RUN apk add --no-cache jq curl

WORKDIR /app

# Requirements zuerst (besseres Layer-Caching)
COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App-Code
COPY app/ /app/

# Startscript
COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 8099

CMD ["/run.sh"]
