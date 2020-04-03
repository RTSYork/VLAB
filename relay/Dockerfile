FROM vlab/vlabcommon

RUN apt-get update

# Prerequisites
RUN apt-get install -y redis-server

EXPOSE 22
EXPOSE 6379

#node.js, npm, and Frontail
RUN apt-get -y install curl gnupg
RUN curl -sL https://deb.nodesource.com/setup_12.x | bash -
RUN apt-get -y install nodejs
RUN npm install --production
RUN npm install frontail -g

EXPOSE 9001

# Add files
ADD crontab /etc/cron.d/vlab-cron
RUN crontab /etc/cron.d/vlab-cron
ADD supervisord.conf /etc/supervisor/conf.d/supervisord.conf
ADD *.py /vlab/

# Create user to match host machine for owning keyfiles
RUN useradd -M -d /nonexistent -s /usr/sbin/nologin -u 50000 vlab_keys_owner

CMD ["/usr/bin/supervisord"]
