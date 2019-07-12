#!/bin/bash
cd /home/robo-advisor/
pylivetrader run -f algo.py --backend-config config.yaml >> app.log