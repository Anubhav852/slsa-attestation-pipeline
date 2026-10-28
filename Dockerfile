FROM python:3.11-slim AS builder
WORKDIR /build
COPY app/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim AS runner
WORKDIR /app
RUN groupadd -g 10001 appgroup && useradd -u 10001 -g appgroup -m -s /sbin/nologin appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY app/app.py .
COPY app/static ./static
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN chown -R appuser:appgroup /app /home/appuser \
 && rm -f /bin/sh /bin/bash /bin/dash /bin/rbash /usr/bin/sh /usr/bin/bash /usr/bin/dash /usr/bin/rbash /usr/bin/curl /usr/bin/wget
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python", "app.py"]