FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y openssh-server python3 sudo && \
    mkdir -p /var/run/sshd && \
    echo 'root:root' | chpasswd && \
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    rm -rf /var/lib/apt/lists/*
EXPOSE 22 80 8080
CMD ["/usr/sbin/sshd", "-D"]