FROM python:3-alpine

RUN pip3 install --no-cache-dir pytest requests pyyaml python-dateutil==2.8.1 tx-functional>=0.0.16 tx-parallex>=0.0.38 pint

RUN mkdir /test

WORKDIR /test

COPY data.py /test/data.py
COPY pdspi /test/pdspi
COPY api /test/api
COPY pdsphenotypemapping /test/pdsphenotypemapping
COPY tx-utils/src /test
COPY pdspi /test/pdspi
COPY tests/test_spec/spec.py /test/spec.py
COPY tests/test_spec/data.yaml /test/data.yaml
COPY tests/test_*.py /test/
COPY tests/ptdata /test/ptdata

ENV PYTHONPATH=/test

ENTRYPOINT ["pytest"]
CMD ["-s"]
