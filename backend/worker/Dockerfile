FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
WORKDIR /worker
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.txt
COPY query.py .
ENV HOME=/tmp
USER 65532:65532
ENTRYPOINT ["python", "-I", "-B", "/worker/query.py"]
