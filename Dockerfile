FROM python:3-alpine

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN apk --no-cache add gcc musl-dev libffi-dev file make

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY data.py /usr/src/app/data.py
COPY pdspi /usr/src/app/pdspi
COPY api /usr/src/app/api
COPY pdsphenotypemapping /usr/src/app/pdsphenotypemapping
COPY tx-utils/src /usr/src/app

ENTRYPOINT ["gunicorn"]

CMD ["-w", "4", "-b", "0.0.0.0:8080", "api.server:create_app()", "-t", "3600"]

