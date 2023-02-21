FROM python:3.10-slim
LABEL maintainer="Websoft9<help@websoft9.com>"

# Create api directory
WORKDIR /usr/src/app

# Copy sw and install pip dependencies
COPY api ./api
COPY data/public_schools.db ./data/public_schools.db
COPY requirements.txt main.py docker-entrypoint.sh ./
RUN pip install -r requirements.txt

# Starts our application
CMD ["uvicorn", "main:get_app", "--host", "0.0.0.0", "--port", "5000", "--log-level", "info"]

# Expose the port in which the application will be deployed
EXPOSE 5000
