# Use an official Python runtime as a parent image
FROM python:3.6-slim

# Set the working directory to /app
WORKDIR /app

COPY bin/websocket-proxy.py requirements.txt /app/
COPY lib/micronets-ws-proxy.pkeycert.pem lib/micronets-ws-root.cert.pem /app/lib/

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt

# Make port 5050 available to the world outside this container
EXPOSE 5050

# Run app.py when the container launches
CMD ["python3.6", "websocket-proxy.py"]
