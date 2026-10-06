# A minimal SSH host with one unprivileged user, "ops", that accepts only keys.
FROM alpine:3.22
RUN apk add --no-cache openssh-server \
    && adduser -D -s /bin/sh ops \
    && passwd -u ops \
    && mkdir -p /home/ops/.ssh \
    && chown ops:ops /home/ops/.ssh \
    && chmod 700 /home/ops/.ssh \
    && ssh-keygen -A \
    && printf 'PasswordAuthentication no\nPermitRootLogin no\n' >> /etc/ssh/sshd_config
RUN printf 'edge-host\nregion=eu-west-1\n' > /etc/edge-release
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
