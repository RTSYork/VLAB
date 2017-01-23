FROM vlab/vlabcommon

RUN mkdir /app
COPY requirements.txt /app
RUN pip3 install -r /app/requirements.txt

COPY . /app
WORKDIR /app

ENTRYPOINT ["python3"]
CMD ["app.py"]
