FROM grahamdumpleton/mod-wsgi-docker:python-3.5-onbuild
# For some reason, vault_auth won't install when included in the requirements file so
# it gets explicitly installed here.
RUN pip install git+https://github.com/linaro-its/vault_auth.git
CMD [ "start_app.wsgi" ]
