FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y wget ca-certificates curl nano && \
    wget https://apt.puppet.com/puppet8-release-jammy.deb && \
    dpkg -i puppet8-release-jammy.deb && rm puppet8-release-jammy.deb && \
    apt-get update && apt-get install -y puppet-agent
ENV PATH="/opt/puppetlabs/bin:${PATH}"
CMD ["tail", "-f", "/dev/null"]