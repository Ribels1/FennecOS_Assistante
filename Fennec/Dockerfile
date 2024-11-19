# Base image
FROM python:3.12-slim


WORKDIR /app


COPY . .


RUN pip install pycairo
RUN pip install pyproject
RUN pip install PyGObject
RUN pip install requests


EXPOSE 5000



CMD ["python", "justwork.py"]



