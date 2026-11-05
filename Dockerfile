# hireburn in a container: runs the demo on the synthetic example company by default.
#   docker build -t hireburn .
#   docker run --rm hireburn                                   # demo
#   docker run --rm -v "$PWD:/data" hireburn funnel /data/funnel.csv
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY hireburn ./hireburn
COPY examples ./examples
RUN pip install --no-cache-dir . && useradd --create-home hireburn
USER hireburn
ENTRYPOINT ["hireburn"]
CMD ["demo", "--data", "/app/examples/example-company"]
