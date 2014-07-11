
Introduction
===============

ggpyjobs is the replay-processing engine for the GGTracker site.

Requests for replay processing are queued in Redis by the 'esdb'
codebase; ggpyjobs retrieves these from queue, and performs the
requested parsing work.

This codebase is useful to read if you're wondering how GGTracker
extracts some piece of information from replay files.

If you want GGTracker to show a new piece of information, the steps
include:
* add the necessary processing code here, in ggpyjobs
* modify the GGTracker web + Angular code to show the new piece of
  information


Requirements
===============

 * MySQL
 * Python 2.X
 * Redis


Installation
===============

I'm probably missing some steps here; if you run into problems, please
let me know so I can improve this README.

* create MySQL databases called esdb_development and esdb_test
* sign up for an Amazon AWS account
* `mkdir config`
* `cp config_example/s3.yml config`
* customize config/s3.yml, putting your AWS details in
* `cp config_example/database.yml config`

Install the various requirements. PIL may require external libraries to be installed.

* `pip install -r requirements.txt`


Set up your environment variables
* `GGFACTORY_CACHE_DIR` (required): Sets a directory to cache remote
  files used to load SC2 resources. Use full path.
* `DJANGO_SECRETKEY` (required): Sets the SECRETKEY in the django
  settings.py file.

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
