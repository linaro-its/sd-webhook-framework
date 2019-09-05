# Using WSGI to run the framework

Since WSGI is specific to the version of Python being used and you can only have one mod_wsgi installed per Apache installation, a configuration is provided to make it easy to run the framework in a Docker container and thus isolate it from anything else running on the host.

A `docker-compose.yml` file has been provided to simplify building and starting the container. Before using this, ensure that the required handlers have been copied into the `rt_handlers` directory or you've uncommented the volume mount line in `docker-compose.yml` and pointed it at the directory where the handlers can be found.

Running `sudo docker-compose up` will start the container (building it first if required) and display any output produced from the container. The framework should then be accessible on port 8000 on the host.

To have the framework running in the background, use `sudo docker-compose up -d`.

## Notes

The expectation is that this is all running on the same server as Service Desk and therefore Service Desk/Jira can use `http://localhost:8000`. If that isn't the case, there will be a need to use a web server like Apache or nginx to proxy to the container.

If any of the handlers need to send email (rather than post comments to the issue), there is shared code to simplify this but some additional work is required:

1. If you want to use the MTA on the host system, configure it to listen to all interfaces or add the Docker interface to the list of listened interfaces.

2. Otherwise, run a second container which provides the MTA function and edit `docker-compose.yml` so that it starts both containers and puts them into the same network.
