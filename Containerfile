FROM python:3-alpine

WORKDIR /app

COPY ./src/requirements.txt ./

RUN python3 -m pip install -r ./requirements.txt

COPY src/doit ./

ENTRYPOINT ["python3", "./doit"]
