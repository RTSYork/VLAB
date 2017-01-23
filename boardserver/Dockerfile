FROM vlab/vlabcommon

#This should be set to the name of the Xilinx Hardware Server installer without the .tar.gz extension. 
#Example: "Xilinx_HW_Server_Lin_2016.2_0605_1"
ARG HWFILE

#Prerequisites
RUN apt-get install -y gcc-multilib openjdk-7-jre libxtst6 screen

#Install the Xilinx hardware server
ADD "${HWFILE}.tar.gz" /root/
#ADD "Xilinx_HW_Server_Lin_2016.2_0605_1.tar.gz" /root/
RUN cd /root/${HWFILE}; ./xsetup --agree XilinxEULA,3rdPartyEULA,WebTalkTerms -b Install -e "Hardware Server (Standalone)"
RUN cd /; rm -rf /root/${HWFILE}

#Add the VLAB internal ssh key
ADD authorized_keys /root/.ssh/
RUN chmod 700 /root/.ssh
RUN chmod 600 /root/.ssh/authorized_keys

#Scripts
ADD supervisord.conf /etc/supervisor/conf.d/supervisord.conf
ADD *.py /vlab/

EXPOSE 22 

CMD ["/usr/bin/supervisord"]
