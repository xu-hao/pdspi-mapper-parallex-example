FROM python:3-alpine

RUN pip3 install --no-cache-dir pytest requests pyyaml tx-functional

RUN mkdir /test

WORKDIR /test

COPY tx-utils/src/tx /test/tx
COPY pdspi /test/pdspi
COPY tests/test_func.py /test/test_func.py
COPY tests/ptdata /test/ptdata

ENTRYPOINT ["pytest"]
CMD ["-s"]
