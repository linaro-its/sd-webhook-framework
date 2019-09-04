# Using WSGI to run the framework

Since WSGI is specific to the version of Python being used and you can only have one mod_wsgi installed per Apache installation, a Docker container is used to isolate everything we need to run the framework.

Whilst in the framework repo directory, run:

`docker build -t sd-webhook .`

Note that for this to work, you must either have copied the required handlers into the `rt_handlers` directory or symlinked them from the sd-webhook-handlers directory/repo.

Then, to run everything:

`docker run -it --rm -p 8000:80 --name sd-webhook sd-webhook`

The framework should then be accessible on port 8000 on the host.
