import os, sys

import yaml
from django.conf import settings

# Mock options.path for tests run from within the vendor/ggpyjobs directory?
try:
  from __main__ import options
except ImportError:
  from optparse import OptionParser
  parser = OptionParser()
  (options, args) = parser.parse_args()
  options.path = '../../'

# http://stackoverflow.com/questions/42558/python-and-the-singleton-pattern
def singleton(cls):
  instances = {}
  def getinstance():
    if cls not in instances:
      instances[cls] = cls()
    return instances[cls]
  return getinstance

def django_setup():
  print "Setting up Django.."

  os.environ['DJANGO_SECRETKEY'] = ''
  os.environ['S3_KEY'] = ''
  os.environ['S3_SECRET'] = ''
  os.environ['S3_MINIMAP_BUCKET'] = ''
  os.environ['S3_REPLAY_BUCKET'] = ''
  env = os.environ['RACK_ENV'] = os.environ.get('RACK_ENV', 'development')

  # test configuration is specified via the django-standard settings.py
  # however dev and prod configuration is specified in the block below
  if 'test' not in sys.argv:
    # for dev and prod, we are launched from the esdb root directory
    dbcfg = yaml.load(open(options.path + '/config/database.yml'))
    s3cfg = yaml.load(open(options.path + '/config/s3.yml'))
    rediscfg = yaml.load(open(options.path + '/config/redis.yml'))
    token_cfg = yaml.load(open(options.path + '/config/tokens.yml'))

    settings.configure(
      DATABASES = {
        'default': {
          'ENGINE': 'django.db.backends.mysql', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
          'NAME': dbcfg[env]['database'],                      # Or path to database file if using sqlite3.
          'USER': dbcfg[env]['username'],                      # Not used with sqlite3.
          'PASSWORD': dbcfg[env]['password'],   # Not used with sqlite3.
          'HOST': dbcfg[env]['host'],                      # Set to empty string for localhost. Not used with sqlite3.
          'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
          }
        },
      DEBUG=True,
      AWS_ACCESS_KEY_ID = s3cfg[env]['minimaps']['access_key_id'],
      AWS_SECRET_ACCESS_KEY = s3cfg[env]['minimaps']['secret_access_key'],
      MINIMAP_BUCKET_NAME = s3cfg[env]['minimaps']['bucket'],
      S2GS_BUCKET_NAME = 'foo',
      REPLAY_BUCKET_NAME = s3cfg[env]['replays']['bucket'],
      BLOB_BUCKET_NAME = s3cfg[env]['matchblobs']['bucket'],
      
      # Yea, screw it, we'll just misuse django :)
      REDIS_SERVER = rediscfg[env]['host'] + ':' + str(rediscfg[env]['port']),

      WCS_TOKEN = token_cfg['wcs_token'],
      WCS_TOKEN_2 = token_cfg['wcs_token_2'],
      ESL_TOKEN = token_cfg['esl_token']
    )

  # Add vendor to the path, who cares if it is twice
  root_dir = os.path.abspath(os.path.dirname(__file__))
  sys.path.insert(0, os.path.join(root_dir, '..', 'vendor'))
