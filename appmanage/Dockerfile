FROM python:3.10-slim
LABEL maintainer="Websoft9<help@websoft9.com>"

# Create API Directory
WORKDIR /usr/src/app

# Copy source and install pip dpendencies
COPY api ./api
COPY static ./static
COPY requirements.txt main.py  ./
RUN apt update

# Install supervisord
RUN apt install -y supervisor
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY config/cmd.sh /cmd.sh
RUN chmod +x /etc/supervisor/conf.d/supervisord.conf /cmd.sh
RUN pip install -r requirements.txt
RUN mkdir /data

# Expose the port in which the application will be deployed
EXPOSE 5000