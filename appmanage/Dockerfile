FROM python:3.10-slim
LABEL maintainer="Websoft9<help@websoft9.com>"

# Create api directory 
WORKDIR /usr/src/app

# Copy source and install pip dependencies
COPY api ./api
COPY static ./static
COPY requirements.txt main.py  ./
RUN apt update
# install supervisord
RUN apt install -y supervisor
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY config/cmd.sh /cmd.sh
RUN chmod +x /etc/supervisor/conf.d/supervisord.conf /cmd.sh
RUN pip install -r requirements.txt
RUN mkdir /data

# Start our application
# CMD ["uvicorn", "main:get_app", "--host", "0.0.0.0", "--port", "5000", "--log-level", "info"]

# Expose the port in which the application will be deployed
EXPOSE 5000
