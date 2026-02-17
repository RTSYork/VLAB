FROM vlab/vlabcommon

# This should be set to the name of the Vivado Lab Solutions installer without the .tar extension.
# Example: "Vivado_Lab_Lin_2025.2_1229_2131"
ARG HWFILE

RUN apt-get update

# Prerequisites
RUN apt-get install -y gcc-multilib openjdk-17-jre libxtst6 screen psmisc locales

# Set locales to US to keep the Xilinx tools happy
RUN locale-gen en_US.UTF-8  
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8 

# Install Vivado Lab Solutions (includes hw_server)
ADD "${HWFILE}.tar" /root/
RUN cd /root/${HWFILE}; ./xsetup --agree XilinxEULA,3rdPartyEULA -b Install -e "Vivado Lab Edition (Standalone)" -l "/opt/Xilinx"
RUN cd /; rm -rf /root/${HWFILE}
RUN mkdir -p /opt/Xilinx/Vivado_Lab && ln -s /opt/Xilinx/*/Vivado_Lab /opt/Xilinx/Vivado_Lab/current

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
ADD test/ /vlab/test/

EXPOSE 22 

CMD ["/usr/bin/supervisord"]
