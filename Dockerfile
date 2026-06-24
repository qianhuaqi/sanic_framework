FROM harbor.icaiji.com.cn/2401/kingsha_system

WORKDIR /webapps

ENV LANG en_US.UTF-8

ENV TZ=Asia/Shanghai

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY . .

CMD ["python3", "run.py"]
