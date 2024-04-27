FROM python:3-alpine

WORKDIR /app

COPY ./cli/requirements.txt ./

RUN python3 -m pip install -r ./requirements.txt

COPY cli/grocycli.py ./

ENTRYPOINT ["python3", "./grocycli.py"]
