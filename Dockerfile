FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY app/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim AS runner
WORKDIR /app
RUN groupadd -g 10001 appgroup && useradd -u 10001 -g appgroup -m -s /sbin/nologin appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY app/app.py .
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages:$PYTHONPATH
RUN chown -R appuser:appgroup /app /home/appuser
RUN rm -rf /bin/bash /bin/sh /usr/bin/curl /usr/bin/wget
USER 10001:10001
EXPOSE 8080
ENV FLASK_ENV=production
ENTRYPOINT ["python", "app.py"]