FROM vlab/vlabcommon

RUN apt-get update; apt-get install -y python3-pip

RUN mkdir /app
COPY requirements.txt /app
RUN pip3 install -r /app/requirements.txt

COPY . /app
WORKDIR /app

ENTRYPOINT ["python3"]
CMD ["app.py"]
