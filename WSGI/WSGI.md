# Using WSGI to run the framework

`mod_wsgi` needs to be specific to the version of Python being used. To simplify this, it has been added to `Pipfile`. In order for it to be installable through that process, it is necessary to install `apache2-dev` and `python3-dev`.

A sample Apache configuration file has been included; this needs to be modified to point to the location of the repo so that WSGI knows where to find things. It is **only** a sample, containing the core WSGI directives required. You may want to include other directives like logs, etc.

Also, there is a simple `app.wsgi` file that is run and that also needs to be updated with the appropriate path information.
