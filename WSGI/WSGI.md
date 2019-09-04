# Using WSGI to run the framework

Since WSGI is specific to the version of Python being used and you can only have one mod_wsgi installed per Apache installation, a Docker container is used to isolate everything we need to run the framework.

Whilst in the WSGI directory, run:

`docker build -t <container-name> .`

Then, to run everything:

`docker run -it --rm -p 8000:80 --name <app-name> -v <path to repo>:/srv/sd-webhook-framework -v <path to handlers>:/srv/sd-webhook-handlers <container-name>`

The framework should then be accessible on port 8000 on the host.
