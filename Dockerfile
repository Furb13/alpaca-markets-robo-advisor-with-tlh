FROM alpacamarkets/pylivetrader

WORKDIR /home/robo-advisor
ADD ./src/ /home/robo-advisor

RUN apt-get update && apt-get install -y
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install --upgrade pipeline-live

RUN ["chmod", "+x", "/home/robo-advisor/docker-entrypoint.sh"]

ENTRYPOINT ["/home/robo-advisor/docker-entrypoint.sh"]