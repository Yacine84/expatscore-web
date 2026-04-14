FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir requests && \
    rm -rf /root/.cache/pip

RUN mkdir -p /app/data && chmod 777 /app/data

COPY reddit_scraper.py .

CMD ["python", "reddit_scraper.py"]