FROM python:3.6
ADD . /tinytextbot/
WORKDIR /tinytextbot
RUN pip install -r requirements.txt
ENV FLASK_APP application.py
CMD ["flask", "run", "--host=0.0.0.0"]