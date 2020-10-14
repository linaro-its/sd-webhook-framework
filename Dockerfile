FROM python:3

RUN apt-get update && \
    apt-get install -y --no-install-recommends apache2 apache2-dev locales && \
    apt-get clean && \
    rm -r /var/lib/apt/lists/*

RUN echo 'en_US.UTF-8 UTF-8' >> /etc/locale.gen && locale-gen

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

RUN pip install -U pip setuptools wheel
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
RUN pip install git+https://github.com/linaro-its/vault_auth.git

WORKDIR /app
COPY . /app
RUN chown -R www-data:www-data /app

# Validate the configuration file
RUN python3 /app/validate_config.py

EXPOSE 8000
USER www-data
CMD ["mod_wsgi-express", "start-server", "--log-to-terminal", "--startup-log", "start_app.wsgi"]
