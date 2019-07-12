FROM alpacamarkets/pylivetrader

WORKDIR /home/app
ADD ./src/ /home/app

RUN apt-get update && apt-get install -y 
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install --upgrade pipeline-live

RUN ["chmod", "+x", "/home/app/docker-entrypoint.sh"]

ENTRYPOINT ["/home/app/docker-entrypoint.sh"]