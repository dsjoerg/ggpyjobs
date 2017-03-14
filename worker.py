#!/usr/bin/env python
# 
# This is using daemon.py from https://github.com/serverdensity/python-daemon

from pyres.worker import Worker
import logging
from pyres import setup_logging, setup_pidfile

import yaml
from daemon import Daemon
import os, sys, inspect, time, socket, errno
from datetime import datetime
import simplejson

# Deprecated, maintaining 2.6 compat here though
# http://docs.python.org/library/optparse.html
from optparse import OptionParser

class gg(Daemon):
  def run(self):
    import ggtracker

    from ggtracker.utils import django_setup
    from django.conf import settings

    django_setup()

    if options.logfile != '':
      setup_logging(procname="pyres_worker", log_level='INFO', filename=options.logfile)
    else:
      setup_logging(procname="pyres_worker", log_level='INFO')
    
    # setup_pidfile(options.pidfile)
    Worker.run(['python', 'python-low', 'python-bg'], settings.REDIS_SERVER, timeout=600)

if __name__ == "__main__":
  parser = OptionParser()
  parser.add_option("-p", "--path", dest="path", help="application root path", metavar="APP_ROOT", default=".")
  parser.add_option("-e", "--env", dest="env", help="application environment", metavar="RACK_ENV", default="development")
  parser.add_option("-i", "--pidfile", dest="pidfile", help="pid file", default="/tmp/gg.pid")
  parser.add_option("-l", "--logfile", dest="logfile", help="log file", default="")

  (options, args) = parser.parse_args()

  if options.env:
    os.environ['RACK_ENV'] = options.env

  if options.path:
    os.environ['APP_ROOT'] = options.path

  daemon = gg(options.pidfile)
  if len(args) >= 1:
    if 'start' == args[0]:
      daemon.start()
    elif 'stop' == args[0]:
      daemon.stop()
    elif 'restart' == args[0]:
      daemon.restart()
    elif 'run' == args[0]:
      daemon.run()
    else:
      print "Unknown command"
      sys.exit(2)

    sys.exit(0)
  else:
    print "usage: %s start|stop|restart" % sys.argv[0]
    sys.exit(2)
