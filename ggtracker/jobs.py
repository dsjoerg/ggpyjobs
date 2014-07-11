from StringIO import StringIO
import urllib2
from datetime import datetime

import hashlib
import json
import logging
import re
import sys, os
import traceback
import urllib

from ggtracker.utils import django_setup
from django.conf import settings
from sc2parse import ggfactory

# S3
import boto
from boto.s3.key import Key

from pyres import ResQ

from sc2parse.sc2reader_to_esdb import SC2ReaderToEsdb

# Setup failure backends for pyres
from pyres import failure

from pyres.failure.multiple import MultipleBackend
from pyres.failure.redis import RedisBackend

failure.backend = MultipleBackend
failure.backend.classes = [RedisBackend]

class ParseReplay():

  @staticmethod
  def perform(args):
    performStart = datetime.now()
    md5 = None
    replayDB = None

    try:
      sc2reader_to_esdb = SC2ReaderToEsdb()

      #
      # at this point the 'hash' may actually be an S3 key like '/uploads/1234-5667-1234234/filename.sc2replay'
      # or simply '{md5}'
      #
      # not to worry, in a few lines, we'll rename the S3 key to be md5.sc2replay
      #
      filename = args['hash']
      if re.search('.sc2replay', filename, re.IGNORECASE) is None:
        filename = filename + ".SC2Replay"

      bucket = boto.connect_s3(settings.AWS_ACCESS_KEY_ID,
                               settings.AWS_SECRET_ACCESS_KEY)\
                               .get_bucket(settings.REPLAY_BUCKET_NAME)

      # logging.getLogger("jobs").info("trying to get key {}".format(filename));
      k = bucket.get_key(filename)

      replaystring = k.get_contents_as_string()
      md5 = hashlib.md5(replaystring).hexdigest()

      #
      # rename the S3 key to simply be md5.SC2Replay, so it's easier for us to find it
      # when we need it.
      #
      # http://stackoverflow.com/questions/2481685/amazon-s3-boto-how-to-rename-a-file-in-a-bucket
      k.copy(settings.REPLAY_BUCKET_NAME, md5 + ".SC2Replay",
             metadata=None, preserve_acl=False)

      replayDB, blob = sc2reader_to_esdb.processReplay(StringIO(replaystring), args['channel'])

      if len(blob) > 0:
        blobbucket = boto.connect_s3(settings.AWS_ACCESS_KEY_ID,
                                     settings.AWS_SECRET_ACCESS_KEY)\
                                     .get_bucket(settings.BLOB_BUCKET_NAME)
        k = Key(blobbucket)
        k.key = "%i" % (replayDB.match.id)
        blobdump = json.dumps(blob)
        k.set_contents_from_string(blobdump)

    except Exception as e:
      tb = traceback.format_exc()
      exc_type, exc_obj, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]      
      logging.getLogger("jobs").info("parsing failed for replay {}. oh well. exception={}. {} {} {} {}".format(args['hash'].encode('ascii'), e, exc_type, fname, exc_tb.tb_lineno, tb))
      pass

    finally:
      alldone = datetime.now()

      # Enqueue ruby PostParse job, always.
      ResQ(server=settings.REDIS_SERVER).enqueue_from_string('ESDB::Jobs::Sc2::Replay::PostParse', 'replays-high', {
        'uuid': args['uuid'],
        'hash': md5,
        'provider_id': str(args['provider_id']),
        'ggtracker_received_at': args['ggtracker_received_at'],
        'esdb_received_at': args['esdb_received_at'],
        'preparse_received_at': args['preparse_received_at'],
        'jobspy_received_at': performStart.strftime('%s.%f'),
        'jobspy_done_at': alldone.strftime('%s.%f'),
      })

      # regarding converting times to floating point seconds since the
      # epoch, using %s above is dangerous because its not python, it
      # calls the underlying OS.  i tried using the solution here:
      # http://stackoverflow.com/questions/6999726/python-getting-millis-since-epoch-from-datetime/11111177#11111177
      # but i ran into timezone issues and did the lazy thing instead.

      matchId = 0
      if replayDB and hasattr(replayDB, "match") and replayDB.match.id:
        matchId = replayDB.match.id
      logging.getLogger("jobs").info("all done with match {}. total time in ParseReplay.perform() = {}".format(matchId, alldone - performStart))

class ParseSummary():

  @staticmethod
  def perform(args):
    try:
      sc2reader_to_esdb = SC2ReaderToEsdb()
      filename = args['hash'] + '.s2gs'
      gateway = args['gateway']
      if gateway == 'sea':
        gateway = 'sg'

      # retrieve it from battlenet
      depoturl = 'http://{0}.depot.battle.net:1119/{1}'.format(gateway, filename)
      try:
        s2gsfile = urllib2.urlopen(depoturl).read()
      except:
        logging.getLogger("jobs").info("couldnt retrieve {} s2gs hash {}. maybe its bad.".format(gateway, args['hash']))
        return None

      # save it in S3 because we are pack rats
      bucket = boto.connect_s3(settings.AWS_ACCESS_KEY_ID,
                               settings.AWS_SECRET_ACCESS_KEY)\
                               .get_bucket(settings.S2GS_BUCKET_NAME)
      k = Key(bucket)
      k.key = filename
      k.set_contents_from_string(s2gsfile)

      # parse it and write stuff to DB
      summaryDB = sc2reader_to_esdb.processSummary(StringIO(s2gsfile), args['hash'])
      
    except Exception as e:
      tb = traceback.format_exc()
      exc_type, exc_obj, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]      
      logging.getLogger("jobs").info("parsing failed for s2gs {}. oh well. exception={}. {} {} {} {}".format(args['hash'], e, exc_type, fname, exc_tb.tb_lineno, tb))
      pass

    finally:
      # Enqueue ruby PostParse job, always!
      ResQ(server=settings.REDIS_SERVER).enqueue_from_string('ESDB::Jobs::Sc2::Summary::PostParse', 'summaries-high', {
        'hash': args['hash']
      })

class ComputeStats():

  @staticmethod
  def perform(args):
    try:
      env = os.environ['RACK_ENV'] = os.environ.get('RACK_ENV', 'development')
      match_id = args['match_id']

      sc2reader_to_esdb = SC2ReaderToEsdb()
      ggthost = 'ggtracker.com'
      blobenv = 'prod'

      if env == 'development':
        ggthost = 'localhost:3000'
        blobenv = 'dev'

      replay = ggfactory.load_replay("http://{}/matches/{}/replay".format(ggthost, match_id))
      url = urllib.urlopen("http://gg2-matchblobs-{}.s3.amazonaws.com/{}".format(blobenv, match_id))

      mb_string = url.read()
      blob = json.loads(mb_string)

      unicode_ident_ids = blob['MineralsCollectionRate'].keys()
      for blobkey in ['MineralsCollectionRate', 'VespeneCollectionRate', 'WorkersActiveCount']:
        for ident_id in unicode_ident_ids:
          blob[blobkey][int(ident_id)] = blob[blobkey][ident_id]

      sc2reader_to_esdb.reprocessEntityStatsForAllPlayers(replay, blob)

    except Exception as e:
      tb = traceback.format_exc()
      exc_type, exc_obj, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]      
      logging.getLogger("jobs").info("stats computation failed for replay {}. oh well. exception={}. {} {} {} {}".format(args['hash'], e, exc_type, fname, exc_tb.tb_lineno, tb))
      pass
      
