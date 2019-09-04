# Using WSGI to run the framework

Since WSGI is specific to the version of Python being used and you can only have one mod_wsgi installed per Apache installation, a Docker container is used to isolate everything we need to run the framework.

A `docker-compose.yml` file has been provided to simplify building and starting the container. Before using this, ensure that the required handlers have been copied into the `rt_handlers` directory or they've been symlinked form the `sd-webhook-handlers` directory/repo.

Running `sudo docker-compose up` will start the container (building it first if required) and display any output produced from the container. The framework should then be accessible on port 8000 on the host.

To have the framework running in the background, use `sudo docker-compose up -d`.

Note: the expectation is that this is all running on the same server as Service Desk and therefore Service Desk/Jira can use `http://localhost:8000`. If that isn't the case, there will be a need to use a web server like Apache or nginx to proxy to the container.
