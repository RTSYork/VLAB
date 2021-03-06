FROM vlab/vlabcommon

# This should be set to the name of the Xilinx Hardware Server installer without the .tar.gz extension.
# Example: "Xilinx_HW_Server_Lin_2016.2_0605_1"
ARG HWFILE

RUN apt-get update

# Prerequisites
RUN apt-get install -y gcc-multilib openjdk-8-jre libxtst6 screen psmisc locales

# Set locales to US to keep the Xilinx tools happy
RUN locale-gen en_US.UTF-8  
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8 

# Install the Xilinx hardware server
ADD "${HWFILE}.tar.gz" /root/
RUN cd /root/${HWFILE}; ./xsetup --agree XilinxEULA,3rdPartyEULA,WebTalkTerms -b Install -e "Hardware Server (Standalone)" -l "/opt/Xilinx"
RUN cd /; rm -rf /root/${HWFILE}
RUN ln -s /opt/Xilinx/HWSRVR/*/ /opt/Xilinx/HWSRVR/current

# Add the VLAB internal ssh key
ADD authorized_keys /root/.ssh/
RUN chmod 700 /root/.ssh
RUN chmod 600 /root/.ssh/authorized_keys

# Prevent locales from being forwarded to the boardserver SSH session
RUN sed -i 's/^AcceptEnv LANG LC_/#AcceptEnv LANG LC_/' /etc/ssh/sshd_config

# Prevent spawning additional Bash sessions from within Screen
RUN echo "trap exit INT; if [ ! -z \"\$STY\" ]; then echo ಠ_ಠ Nothing to see here...; sleep 1; exit; fi; trap - INT" >> /root/.bashrc

# Scripts
ADD supervisord.conf /etc/supervisor/conf.d/supervisord.conf
ADD *.py /vlab/
ADD *.tcl /vlab/
ADD reset.bin /vlab/

EXPOSE 22 

CMD ["/usr/bin/supervisord"]
