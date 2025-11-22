FROM python:3.12

WORKDIR /catty-app

COPY . .

RUN pip install -r requirements.txt

EXPOSE 8181

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8181"]