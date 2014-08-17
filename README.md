Introduction
===============

ggpyjobs is the replay-processing engine for the GGTracker site.

Requests for replay processing are queued in Redis by the 'esdb'
codebase; ggpyjobs retrieves these from queue, and performs the
requested parsing work.

This codebase is useful to read if you're wondering how GGTracker
extracts information from replay files.  See the 'Plugins' section
below.

If you want GGTracker to show a new piece of information, the steps to
do that include:
* add the necessary processing code here, in ggpyjobs
* modify the other parts of GGTracker to work correctly with the new
  piece of information

The other codebases used in GGTracker are:
* https://github.com/dsjoerg/ggtracker <-- the web server and
  HTML/CSS/Javascript for the site
* https://github.com/dsjoerg/esdb <-- the API server
* https://github.com/dsjoerg/gg <-- little gem for accessing ESDB,
  used by the ggtracker codebase


Plugins
===============

ggpyjobs uses the [sc2reader](https://github.com/graylinkim/sc2reader)
library to parse replays.

In sc2parse/plugins.py there are various 'plugins' to sc2reader that compute additional things from each replay file.

The plugins are:
* EngagementTracker -- identifies major combat engagements and
  measures total value of things lost by each player
* ZergMacroTracker -- measures inject efficiency, and active inject
  time per base; distinguishes 'macro hatches'
* ProtossTerranMacroTracker -- tracks energy for each nexus and
  orbital, measures time spent at max energy
* MiningBaseIdentifier -- identifies which bases are in mining
  locations (as opposed to, for example, macro hatches)
* ScoutingTracker -- detects when the first scout command was issued
  to a worker
* UpgradesTracker -- retrieves the list of upgrades and timings per
  player
* ArmyTracker -- retrieves total and per-minute unit counts
* WWPMTracker -- measures 'worker waves per minute', no longer displayed on GGTracker
* BaseTracker -- no longer used since 2.0.8
* TrainingTracker -- no longer used since 2.0.8
* ActivityTracker -- no longer used since 2.0.8
* OwnershipTracker -- no longer used since 2.0.8
* LifeSpanTracker -- no longer used since 2.0.8


Requirements
===============

 * MySQL
 * Python 2.X
 * Redis (when running as part of GGTracker)


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
* `mkdir testcache`

Install the various requirements. PIL may require external libraries to be installed.

* `pip install -r requirements.txt`

Run the tests to verify a successful setup:
> GGFACTORY_CACHE_DIR=testcache GGPYJOBS_CONFIG_PATH=config DJANGO_SECRETKEY=foo ./manage.py test sc2parse

There will be some output; at the end, if all is well, it will say something like:
```
Ran 26 tests in 41.357s

OK
```

Run specific tests like this:
> GGFACTORY_CACHE_DIR=testcache GGPYJOBS_CONFIG_PATH=config DJANGO_SECRETKEY=foo ./manage.py test sc2parse.SC2ReaderToEsdbTestCase.test_close_replays


Parsing a replay with the extra ggpyjobs plugins
================================================
```
GGFACTORY_CACHE_DIR=testcache python
from sc2parse import ggfactory
replay = ggfactory.load_replay('/path/to/a/replay.SC2Replay')
print replay.players[0].upgrades
print replay.eblob
```


Environment Variables
======================

As you may have noticed in the test-running commands above, ggpyjobs
uses the following environment variables:
* `GGFACTORY_CACHE_DIR` (required): Sets a directory to cache remote
  files used to load SC2 resources. Use full path.
* `DJANGO_SECRETKEY` (required): Sets the SECRETKEY in the django
  settings.py file.
* `GGPYJOBS_CONFIG_PATH` (required in testing): The directory where
  the config files s3.yml and database.yml are found for test runs.


Keeping up to Date
=====================

If there are changes to the `requirements.txt` file, run this:

> $ pip install --upgrade -r requirements.txt



Working on sc2reader
========================

If you want ggpyjobs to use a customized version of sc2reader:

> $ pip uninstall sc2reader
> $ cd path/to/ggtracker/sc2reader
> $ python setup.py develop

When installed in this 'develop mode', sc2reader will automatically
reflect changes to the code base it was installed from. Please note
that a worker running as a daemon will *not* automatically reflect
changes to the code made since the process began running. The worker
must be shut down and restarted to pick up the code changes.


### I don't understand XXXX

Just ask, I'll add questions and answers to a FAQ here.

