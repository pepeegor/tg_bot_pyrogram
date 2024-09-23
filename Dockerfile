FROM python:3.11.6-slim

ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

RUN apt-get update

RUN mkdir /tg_bot

WORKDIR /tg_bot

COPY --from=ghcr.io/ufoscout/docker-compose-wait:latest /wait /wait

COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

CMD ["python3", "main.py"]
