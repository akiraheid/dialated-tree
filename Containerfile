FROM python:3-alpine

COPY src/* /app/

RUN python3 -m pip install -r /app/requirements.txt

WORKDIR /app

ENTRYPOINT ["python3", "./doit"]
