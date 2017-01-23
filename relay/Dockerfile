FROM vlab/vlabcommon

#Prerequisites
RUN apt-get install -y redis-server

EXPOSE 22
EXPOSE 6379

#Add files
ADD crontab /etc/cron.d/vlab-cron
ADD supervisord.conf /etc/supervisor/conf.d/supervisord.conf
ADD *.py /vlab/

CMD ["/usr/bin/supervisord"]
