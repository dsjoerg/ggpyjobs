Retrieve jobs queued by ruby in python, and perform the requested parsing work.

Installation
===============

**TODO** - give commands to set up an acceptable directory structure, with config containing what is needed

Install the various requirements. PIL may require external libraries to be installed.

> $ pip install -r requirements.txt

Set up database configuration

**TODO** - describe how config/database.yml must be symlinked to the containing (esdb) directory.
**TODO** - give steps to set up AWS for testing


Set up your environment variables

* `GGFACTORY_CACHE_DIR` (required): Sets a directory to cache remote files used to load SC2 resources. Use full path.
* `DJANGO_SECRETKEY` (required): Sets the SECRETKEY in the django settings.py file.

Run the tests to verify a successful setup:

> GGFACTORY_CACHE_DIR=testcache ./manage.py test sc2parse

Run specific tests like this:
> GGFACTORY_CACHE_DIR=testcache ./manage.py test sc2parse.SC2ReaderToEsdbTestCase.test_close_replays


Keeping up to Date
=====================

When you pull down changes to the `requirements.txt` file:

> $ pip install --upgrade -r requirements.txt



Working on sc2reader
========================

Development work on sc2reader requires a manual uninstall of the
sc2reader version installed by the requirements file followed by
an installation from a local copy of the ggtracker/sc2reader repo.

> $ pip uninstall sc2reader
> $ cd path/to/ggtracker/sc2reader
> $ python setup.py develop

When installed in develop mode sc2reader will automatically reflect
changes to the code base it was installed from. Please note that
a worker running as a daemon will *not* automatically reflect changes
to the code made since the process began running. The worker must be
shut down and restarted to pick up the code changes.

Git
===
Miserable.
