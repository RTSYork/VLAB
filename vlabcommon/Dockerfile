FROM ubuntu:xenial

#Prerequisites
RUN apt-get update; apt-get install -y openssh-server supervisor python3-pip cron
RUN pip3 install redis

#Enable SSHD
RUN mkdir -p /var/log/supervisor /root/.ssh /var/run/sshd
RUN chmod 700 /root/.ssh
RUN chmod 0755 /var/run/sshd
RUN sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed -i '/pam_motd.so/s/^/#/' /etc/pam.d/sshd

#For cron
RUN touch /etc/cron.d/vlab-cron
RUN chmod 644 /etc/cron.d/vlab-cron

#VLAB scripts directory and logs
RUN mkdir -p /vlab
RUN chmod -R 755 /vlab
RUN touch /var/log/vlab.log

#Common libs
ADD *.py /vlab/
