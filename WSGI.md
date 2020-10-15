# Using WSGI to run the framework

Since WSGI is specific to the version of Python being used and you can only have one mod_wsgi installed per Apache installation, a configuration is provided to make it easy to run the framework in a Docker container and thus isolate it from anything else running on the host.

A `docker-compose.yml` file has been provided to simplify building and starting the container. Before using this, ensure that the required handlers have been copied into the `rt_handlers` directory or you've uncommented the volume mount line in `docker-compose.yml` and pointed it at the directory where the handlers can be found.

Running `sudo docker-compose up` will start the container (building it first if required) and display any output produced from the container. The framework should then be accessible on port 8000 on the host.

To have the framework running in the background, use `sudo docker-compose up -d`.

## Debugging

VS Code has excellent support for debugging code running inside containers and this is the recommended tool. However, WSGI is automatically started when using the container approach, which can make debugging tricky. To avoid that complexity, it is suggested that VS Code is used to run the framework as a Flask application, which listens on a different port (5000) by default, allowing it to be run at the same time. All that needs to change is the webhook endpoint in Service Desk/Jira and then restart Service Desk because it "holds onto" the old endpoint details.

If the container is running on a separate computer, see <https://code.visualstudio.com/docs/remote/containers-advanced#_developing-inside-a-container-on-a-remote-docker-host>. After configuring VS Code appropriately, it will be possible to connect to the running container and then, from there, launch the Flask debugging process.

## Notes

* The expectation is that this is all running on the same server as Service Desk and therefore Service Desk/Jira can use `http://localhost:8000`. If that isn't the case, there will be a need to use a web server like Apache or nginx to proxy to the container since it is likely that SSL would be required to encrypt communications between Service Desk and the framework.

  * The exception is if Service Desk is being run in a container, in which case the application can use `http://sd_webhook:8000` as the URL.

* If any of the handlers need to send email (rather than post comments to the issue), there is shared code to simplify this but some additional work is required:

  1. If you want to use the MTA on the host system, configure it to (additionally) listen to the Docker bridge interface. Unless altered in `docker-compose.yml`, this will be `172.20.0.0/16`.

  2. Otherwise, run a second container which provides the MTA function and edit `docker-compose.yml` so that it starts both containers and puts them into the same network.

* To rebuild the container, use `sudo docker-compose build` or `sudo docker-compose up --build`
