FROM rapidsai/miniforge-cuda:cuda12.2.2-base-ubuntu22.04-py3.9

RUN apt-get -y --allow-releaseinfo-change update && apt-get -y upgrade && apt-get install -y procps

COPY ./requirements.txt /requirements.txt
RUN pip3 install -U -r /requirements.txt
