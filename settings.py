# Django settings for ggtracker project.

import os
import os.path
import sys
import socket
import yaml

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))

DEBUG = False
TEMPLATE_DEBUG = False

ADMINS = (
    ('David Joerg', 'dsjoerg@ggtracker.com'),
)

MANAGERS = ADMINS

with open(PROJECT_PATH + '/config/database.yml','r') as db_yaml:
    dbcfg = yaml.load(db_yaml)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
            'NAME': dbcfg['development']['database'],                      # Or path to database file if using sqlite3.
            'USER': dbcfg['development']['username'],                      # Not used with sqlite3.
            'PASSWORD': dbcfg['development']['password'],   # Not used with sqlite3.
            'HOST': dbcfg['development']['host'],                      # Set to empty string for localhost. Not used with sqlite3.
            'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
        }
    }

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(PROJECT_PATH, 'staticfiles')
#STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
#    os.path.join(PROJECT_PATH, 'static'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = os.environ['DJANGO_SECRETKEY']

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'ggtracker.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(PROJECT_PATH, 'templates'),
)

INSTALLED_APPS = (
# auth and sessions are removed because they use fields of type longtext,
# which are not supported by the mysql memory engine, which we would like to use
# for unit testing, because we'd like to use raw sql queries for replaysWithPlayerAndStart()
# so pick your poison:
# 1) rewrite replaysWithPlayerAndStart() to not use raw sql, or
# 2) go without the auth and sessions apps.
#
# for now, 2) seems fine.
#
    'django.contrib.contenttypes',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'sc2parse',
    'ajaxuploader',
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

# this config is used _only_ in testing.
# dev and prod config happens in ggtracker/utils.py
env = 'test'
config_path = os.environ['GGPYJOBS_CONFIG_PATH']
s3cfg = yaml.load(open(config_path + '/s3.yml'))
AWS_ACCESS_KEY_ID = s3cfg[env]['minimaps']['access_key_id']
AWS_SECRET_ACCESS_KEY = s3cfg[env]['minimaps']['secret_access_key']
MINIMAP_BUCKET_NAME = s3cfg[env]['minimaps']['bucket']

WCS_TOKEN = 'foo'
WCS_TOKEN_2 = 'bar'
ESL_TOKEN = 'baz'

if socket.gethostname() == "David-Joergs-MacBook-Pro.local":
    from settings_dev import *

# Making tests run acceptably fast.  0.4 seconds instead of 20 seconds.
# http://stackoverflow.com/questions/3096148/how-to-run-djangos-test-database-only-in-memory
SOUTH_TESTS_MIGRATE = False
if 'test' in sys.argv:
    DATABASES['default']['OPTIONS'] = { "init_command": "SET storage_engine=MEMORY, character_set_server=utf8" }
