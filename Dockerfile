FROM python:3.6
ADD tinytextbot/ /tinytextbot/
WORKDIR /tinytextbot
RUN pip install -r requirements.txt
ENV FLASK_APP tinytextbot/application.py
CMD ["flask", "run", "--host=0.0.0.0"]