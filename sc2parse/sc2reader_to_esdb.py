# Built-ins
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from time import strftime
import Image
import StringIO
import hashlib
import json
import logging
import math
import re
import sys
import traceback

# Third Party
import boto
from boto.s3.key import Key
from enum import Enum

# Foo
from models import *
from django.db import transaction, connection
from django.db.models import F
from django.conf import settings

from sc2parse import ggfactory
from sc2parse.plugins import MAX_NUM_UNITS, COUNTS_AS_ARMY, ARMY_MAP, army_strength, get_unit_type
from sc2reader.events import CameraEvent, GetFromHotkeyEvent, SelectionEvent, TargetAbilityEvent, UnitPositionsEvent, PlayerStatsEvent, UnitBornEvent, UnitInitEvent
from sc2reader.utils import Length

FRONTEND_TIME_UNITS = 999.0
FRAMES_UNTIL_LOST = 16 * 30
MAX_HOTKEY_JUMP_FRAMES = 8
MAPHEIGHT = 100

class AggressionLevel(Enum):
  EnemyBaseSeen  = 1
  EnemyBaseClose = 2
  NoMansLand     = 3
  OurBaseClose   = 4
  OurBaseSeen    = 5

class ObjectTrack:
  def __init__(self, obj, x, y, frame):
    self.obj = obj
    self.x = x
    self.y = y
    self.frame = frame

  def __str__(self):
    return "obj={}, x={}, y={}, time={}".format(self.obj, self.x, self.y, Length(seconds=int(self.frame/16)))
    

def normalize_gateway(gateway):
    # This guy: http://sea.battle.net/sc2/en/profile/385029/1/Simon/
    # When you parse an s2gs he was in: 9a1dd0afdc425d9aec51dc0b4f62f3526d9e602355e68b3bf21160c54301d114.s2gs
    # you get fun.players[0].gateway == 'sg'
    #
    # I'll say his gateway is 'sea' and that the s2gs is lying.
    # 'sea' is what battle.net and bnet_scraper expects.
    #
    if gateway == 'sg':
        gateway = 'sea'
    return gateway


def army_map(replay, ptoi):
    """Creates a map of player-identity-id => array of army units in this format:
[ [unit type, finished_at, died_at], [unit type, finished_at, died_at], ... ]
"""
    army_map = dict()
    for player in [p for p in replay.players if p in ptoi]:
        player_army = list()
        for unit in player.units:
            unit_type = get_unit_type(unit)

            if unit_type in ARMY_MAP and unit.finished_at is not None and unit.died_at is not None and not unit.hallucinated:
              if unit_type == 'planetaryfortress':
                # Its not a PF until it finishes upgrading!
                for frame, utype in unit.type_history.items():
                  if utype.name == 'PlanetaryFortress':
                    player_army.append(('planetaryfortress', frame, unit.died_at))
                    break;
              elif unit_type == 'overseer':
                # The overseer spends part of its life as a overlord, split the time
                for frame, utype in unit.type_history.items():
                  if utype.name == 'Overseer':
                    player_army.append(('overlord', unit.finished_at, frame))
                    player_army.append(('overseer', frame, unit.died_at))
                    break;
              elif unit_type == 'broodlord':
                # The broodlord spends part of its life as a corruptor, split the time
                for frame, utype in unit.type_history.items():
                  if utype.name == 'BroodLord':
                    player_army.append(('corruptor', unit.finished_at, frame))
                    player_army.append(('broodlord', frame, unit.died_at))
                    break;
              else:
                # Everyone else gets full credit
                player_army.append((unit_type, unit.finished_at, unit.died_at))

        army_map[ptoi[player]] = player_army
    return army_map



class SC2ReaderToEsdb():

  def processReplay(self, stringio, channel):
    """main entry point for replay processing."""
    processReplayStart = datetime.now()
    hash = hashlib.md5(stringio.getvalue()).hexdigest()

    beforeLoadReplay = datetime.now()
    replay = ggfactory.load_replay(stringio)
    afterLoadReplay = datetime.now()

    blob = dict()
    blob["macro"] = []
    blob["camera"] = []

    cobrand = None
    if u'wcs_token' == channel:
      cobrand = 1
    if u'esl_ist_die_beste' == channel:
      cobrand = 2

    matchDB, created = self.getOrCreateMatchDB(replay, cobrand)
    self.populateMatchFromReplay(replay, matchDB)

    replayDB = self.getOrCreateReplayDB(replay, hash, matchDB)

    if cobrand == 1:
      replayDB.hidden = 1
      replayDB.save()

    playerToIdentityId = {}
    playerToEntity = {}

    for player in replay.players:
      idDB = self.getOrCreateIdentity(player, replay.start_time, replay.gateway, created)
      entityDB = self.getOrCreateEntity(matchDB, idDB)

      if player.toon_id > 0:
        playerToIdentityId[player] = idDB.id
      else:
        playerToIdentityId[player] = 0

      playerToEntity[player] = entityDB

      # print "player={}, idDB={}, p.toon_id={}, idDB.id={}".format(player, idDB, player.toon_id, idDB.id)
      self.populateEntityFromReplay(entityDB, matchDB, player, replay)
      self.populateBlobFromReplay(blob, player, replay, playerToIdentityId)

    self.populateBlobWithCamera(blob, replay, matchDB.map, playerToIdentityId)
    object_tracks = self.trackAllObjects(replay)
    self.populateBlobWithLocations(blob, replay, matchDB.map, playerToIdentityId, object_tracks)
    self.populateBlobWithAggressions(blob, replay, playerToIdentityId, object_tracks)
    blob["armies_by_frame"] = army_map(replay, playerToIdentityId)

    # This also populates replay.player fields.
    self.populateBlobWithSummaryData(blob, replay, playerToIdentityId)

    self.populateBlobWithNumBases(blob, replay, playerToIdentityId)
    self.populateBlobWithScouting(blob, replay, playerToIdentityId)
    self.populateBlobWithUpgrades(blob, replay, playerToIdentityId)
    self.populateBlobWithProtossMacro(blob, replay, playerToIdentityId)
    self.populateBlobWithTerranMacro(blob, replay, playerToIdentityId)

    blob["engagements"] = replay.eblob

    # TODO refactor this into sc2reader as an attribute on the player
    highest_leagues = [player.highest_league for player in replay.humans]

    for player in replay.players:
      entityDB = playerToEntity[player]

      if replay.build >= 25446 and player.toon_id > 0:
          self.deletePlayerSummaryFor(entityDB, player)
          self.createPlayerSummaryFromReplay(entityDB, player)
          self.deleteEntityStatsFor(entityDB, player)
          self.createEntityStatsFor(entityDB, player, highest_leagues, blob, playerToIdentityId[player])

    #TODO set provider of replay based on subdomain or something else?!
    # have to let MLG contribute replays somehow right?

    alldone = datetime.now()
    logging.getLogger("sc2r2esdb").info("processReplay done. replay {}, match {}, loadreplay {}, total timeused {}".format(replayDB.id, matchDB.id, afterLoadReplay - beforeLoadReplay, alldone - processReplayStart))

    return replayDB, blob


  def populateBlobWithSummaryData(self, matchblob, replay, playerToIdentityId):
      # Tracker only useful for post 2.0.8 replays
      if replay.build < 25446: return replay

      identityIdToPlayer = dict([(v,k) for k,v in playerToIdentityId.items()])

      blob_names = ['Lost','VespeneCurrent','MineralsCurrent','VespeneCollectionRate','MineralsCollectionRate','WorkersActiveCount','SupplyUsage']
      for blob_name in blob_names:
          matchblob[blob_name] = defaultdict(list)

      players_we_track = [player for player in playerToIdentityId]
      expected_player_count = len(players_we_track)
      def gatherstats(now, stats, matchblob):
          if len(stats) == expected_player_count:
              for ident_id, pstats in stats.items():
                  matchblob['Lost'][ident_id].append(pstats.resources_lost)
                  matchblob['VespeneCurrent'][ident_id].append(pstats.vespene_current)
                  matchblob['MineralsCurrent'][ident_id].append(pstats.minerals_current)
                  matchblob['VespeneCollectionRate'][ident_id].append(pstats.vespene_collection_rate)
                  matchblob['MineralsCollectionRate'][ident_id].append(pstats.minerals_collection_rate)
                  matchblob['WorkersActiveCount'][ident_id].append(pstats.workers_active_count)
                  matchblob['SupplyUsage'][ident_id].append((pstats.food_used, pstats.food_made))
          else:
              print "Ignoring stats at loop {}, there were only {} but we needed {}".format(now, len(stats), expected_player_count)

      now = 0
      stats = dict()
      efilter = lambda e: isinstance(e, PlayerStatsEvent)
      for event in filter(efilter, replay.tracker_events):
          # The events are sent in blocks ever 10seconds, 1 per player.
          if event.frame != now:
              if stats:
                  gatherstats(now, stats, matchblob)
                  stat = dict()
              now = event.frame

          # TODO: Get the ident_id instead
          if event.player in playerToIdentityId:
              stats[playerToIdentityId[event.player]] = event

      # Gather that last set of stats
      gatherstats(now, stats, matchblob)

      for blob_name, attr_name in dict(
          VespeneCurrent='average_unspent_vespene',
          MineralsCurrent='average_unspent_minerals',
          VespeneCollectionRate='average_vespene_collection_rate',
          MineralsCollectionRate='average_minerals_collection_rate',
      ).iteritems():
          for ident_id, values in matchblob[blob_name].items():
              player = identityIdToPlayer[ident_id]

              # for the purpose of computing averages, we dont want
              # the first value of these arrays, which is the
              # observation at time 0
              values = values[1:]

              setattr(player,attr_name, sum(values)/len(values))

      for player in players_we_track:
          player.average_resource_collection_rate = player.average_vespene_collection_rate + player.average_minerals_collection_rate
          player.average_unspent_resources = player.average_unspent_minerals + player.average_unspent_vespene
          player.workers_created = len([u for u in player.units if (u.is_worker and u.finished_at is not None)])

          # we dont want to count beacons, larva and broodlings as units for the purposes of units_trained
          # what they have in common is that they have no mineral + vespene cost
          # subtract six because the initial workers dont count as units trained
          player.units_trained = len([u for u in player.units if (not u.is_building and u.finished_at is not None and (u.minerals + u.vespene > 0))]) - 6

          # subtract one because the initial base doesnt count as a structure built
          player.structures_built = len([u for u in player.units if (u.is_building and u.finished_at is not None)]) - 1
          player.workers_killed = len([u for u in player.killed_units if u.is_worker])

          # we dont want to count larva or broodlings as units for the purposes of units_killed
          # what they have in common is that they have no mineral + vespene cost
          player.units_killed = len([u for u in player.killed_units if not u.is_building and u.owner is not None and (u.minerals + u.vespene > 0)])

          player.structures_razed = len([u for u in player.killed_units if u.is_building and u.owner is not None])

      if False:
          for player in players_we_track:
              print player,'\n','='*30,'\n'
              for attr_name in ['time_supply_capped','average_resource_collection_rate','average_unspent_resources','workers_created','units_trained','structures_built','workers_killed','units_killed','structures_razed']:
                  print "{0: <33}:\t{1}".format(attr_name, getattr(player, attr_name))
              print
              for blob_name in blob_names:
                  print "{0}:\n{1}\n".format(blob_name, matchblob[blob_name][player.pid])
              print


  def populateBlobWithCamera(self, blob, replay, mapDB, ptoi):
      lastTime = {}
      cameraXPos = {}
      cameraYPos = {}
      for player in [p for p in replay.players if p in ptoi]:
          lastTime[player] = -1
          cameraXPos[ptoi[player]] = []
          cameraYPos[ptoi[player]] = []
      timeFactor = FRONTEND_TIME_UNITS / replay.frames

      for event in replay.events:
          if event.name == "CameraEvent" and (not event.player.is_observer) and (event.player in ptoi):
              nowTime = int(event.frame * timeFactor)
              if nowTime > lastTime[event.player]:
                  imageX = int(mapDB.transX + mapDB.image_scale * event.x)
                  imageY = int(mapDB.transY - mapDB.image_scale * event.y)
                  for i in range(lastTime[event.player]+1, nowTime + 1):
                      cameraXPos[ptoi[event.player]].append(imageX)
                      cameraYPos[ptoi[event.player]].append(imageY)
                  lastTime[event.player] = nowTime

      blob["camera"].append([cameraXPos, cameraYPos])

  # returns a list of [obj, x, y, frame], using all the methods we
  # have for tracking where objects are.
  def trackAllObjects(self, replay):
    lastEvent = dict()
    lastCamera = dict()
    object_tracks = list()

    efilter = lambda e: hasattr(e, 'player') or e.name in ['UnitBornEvent', 'UnitInitEvent', 'UnitPositionsEvent']
    for event in filter(efilter, replay.events):
          if isinstance(event, CameraEvent) and isinstance(lastEvent[event.player], GetFromHotkeyEvent) and event.frame - lastEvent[event.player].frame < MAX_HOTKEY_JUMP_FRAMES:
              for obj in lastEvent[event.player].selected:
                  object_tracks.append(ObjectTrack(obj, event.x, event.y, event.frame))
          if isinstance(event, SelectionEvent) and event.bank == 10 and len(event.objects) > 0 and event.player in lastCamera:
              for obj in event.objects:
                  object_tracks.append(ObjectTrack(obj, lastCamera[event.player][0], lastCamera[event.player][1], event.frame))
          if isinstance(event, TargetAbilityEvent) and event.location is not None:
              object_tracks.append(ObjectTrack(event.target, event.location[0], event.location[1], event.frame))
          if isinstance(event, CameraEvent):
              lastCamera[event.player] = (event.x, event.y)
          if isinstance(event, UnitPositionsEvent):
              for unit, (x,y) in event.units.items():
                object_tracks.append(ObjectTrack(unit, x, y, event.frame))
          if isinstance(event, UnitBornEvent) or isinstance(event, UnitInitEvent):
              object_tracks.append(ObjectTrack(event.unit, event.x, event.y, event.frame))

          if hasattr(event, 'player'):
              lastEvent[event.player] = event

    return object_tracks
    

  # locations is a list of length FRONTEND_TIME_UNITS showing, for
  # each time unit, where various player stuff is
  #
  # deathlocations is a similar list showing for each time unit,
  # deaths that happened at that time.
  def populateBlobWithLocations(self, blob, replay, mapDB, ptoi, object_tracks):
      timeFactor = FRONTEND_TIME_UNITS / replay.frames
      locations = list()
      deathlocations = list()
      trackedunits = dict()

      def mapToImage(x, y):
          imageX = int(mapDB.transX + mapDB.image_scale * x)
          imageY = int(mapDB.transY - mapDB.image_scale * y)
          return imageX, imageY

      lastTime = 0
      lastplayerlocs = None
      trackedPlayers = [p for p in replay.players if p in ptoi]

      for ot in object_tracks:
          nowTime = int(ot.frame * timeFactor)
          if nowTime > lastTime:
              # playerlocs is a dict from identity id to
              #               a dict from location tuple to army strength at that point.
              playerlocs = dict()

              # playerlocdiffs is a dict from identity id to
              #                a list of [location, strength] for each location that had a strength
              #                  change in that timeslice
              playerlocdiffs = dict()

              # playerdeaths is a dict from identity id to a set of
              # location tuples where deaths occurred
              playerdeaths = defaultdict(set)

              for player in trackedPlayers:
                  playerlocs[ptoi[player]] = dict()

              for unit, unitinfo in trackedunits.items():
                  if ot.frame > unit.died_at:
                      if unit.owner is not None and unit.owner in ptoi and (unit.minerals + unit.vespene > 0) and (unit.killed_by is not None or replay.build < 25446):
                          if hasattr(unit, 'location'):
                              # tracker death event sets the unit
                              # location to its final resting place
                              imageX, imageY = mapToImage(unit.location[0], unit.location[1])
                              unitloc = (imageX, imageY)
                          else:
                              unitloc = (unitinfo[1], unitinfo[2])
                          playerdeaths[ptoi[unit.owner]].add(unitloc)
#                          print "BOOM! unit={}, died_at={}, killed_by={}, location=({},{}), imageloc=({},{})".format(unit.name, Length(seconds=int(unit.died_at/16)), unit.killed_by, unit.location[0], unit.location[1], imageX, imageY)
                      del trackedunits[unit]
                  if ot.frame < unit.died_at and unit.owner is not None and unit.owner in ptoi:
                      unitloc = (unitinfo[1], unitinfo[2])
                      if unitloc not in playerlocs[ptoi[unit.owner]]:
                          playerlocs[ptoi[unit.owner]][unitloc] = 0
                      unitname = unit.name.lower()
                      # show everything we can track as at least one strength unit. buildings, drones, whatever
                      strength = 1
                      if COUNTS_AS_ARMY.get(unitname):
                          strength = army_strength(replay.expansion, unitname)
                      playerlocs[ptoi[unit.owner]][unitloc] += strength

              for player in trackedPlayers:
                  outlist = list()
                  outdeaths = list()
                  ident_id = ptoi[player]

                  #print "player={}, ptoi[p]={}, pl[ptoi[p]]={}".format(player, ptoi[player], playerlocs[ptoi[player]])
                  for location, strength in playerlocs[ident_id].iteritems():
                      if lastplayerlocs is None or \
                         location not in lastplayerlocs[ident_id] or \
                         lastplayerlocs[ident_id][location] != strength:
                          outlist.append([location, strength])
                  if lastplayerlocs is not None:
                      for location in lastplayerlocs[ident_id].keys():
                          if location not in playerlocs[ident_id]:
                              outlist.append([location, 0])

                  playerlocdiffs[ident_id] = outlist
                  if ident_id in playerdeaths:
                      playerdeaths[ident_id] = list(playerdeaths[ident_id])

              lastplayerlocs = playerlocs

              for i in range(lastTime+1, nowTime+1):
                  locations.append(playerlocdiffs)
                  deathlocations.append(playerdeaths)
              lastTime = nowTime

          # the standard transform takes camera-center SC2 coords and
          # translates them to upper-left bbox coords for the image.
          imageX, imageY = mapToImage(ot.x, ot.y)
          trackedunits[ot.obj] = (ot.frame, imageX, imageY)
          # print "{}: tracking {} (owner {}) at {}, {} which is {}, {}".format(ot.frame, ot.obj, ot.obj.owner, ot.x, ot.y, imageX, imageY)


      blob["locationdiffs"] = locations
      blob["deathlocations"] = deathlocations

  # Return the distance from the location to the nearest of the given bases.
  # The base must be alive or at least under construction at the given time.
  #
  # will return sqrt(999999) if there are no bases
  #
  def distToNearestBase(self, frame, location, bases):
    min_sq_dist = 999999
    alive_bases = [base for base in bases if frame >= base.started_at and frame <= base.died_at]
    for base in alive_bases:
      deltax = base.location[0] - location[0]
      deltay = base.location[1] - location[1]
      sqdist = deltax * deltax + deltay * deltay
      if sqdist < min_sq_dist:
        min_sq_dist = sqdist
        
    return math.sqrt(min_sq_dist)



  # Return an AggressionLevel indicating the aggression level of that
  # position for the given player at the given time.
  def aggressionFor(self, replay, frame, location, player):
    enemy = next(p for p in replay.players if p != player)
    dist_to_enemy_base = self.distToNearestBase(frame, location, enemy.bases)
    if dist_to_enemy_base <= 10:
      return AggressionLevel.EnemyBaseSeen
    if dist_to_enemy_base <= 40:
      return AggressionLevel.EnemyBaseClose
    
    dist_to_our_base = self.distToNearestBase(frame, location, player.bases)
    if dist_to_our_base <= 10:
      return AggressionLevel.OurBaseSeen
    if dist_to_our_base <= 40:
      return AggressionLevel.OurBaseClose

    return AggressionLevel.NoMansLand
    

  # aggressions is a map of player to
  # a list of aggression snapshots.  each aggression snapshot is a list:
  # [ frame,
  #   enemy-base-seen,
  #   enemy-base-close,
  #   no-mans-land,
  #   our-base-close,
  #   our-base-seen
  # ]
  #
  def computeAggressions(self, replay, object_tracks):

    snapshot_frequency = 5 * 16

    aggressions = dict()
    for player in replay.players:
      aggressions[player] = list()

    trackedunits = dict()
    last_snapshot_frame = 0
    for ot in object_tracks:
      if ot.frame - last_snapshot_frame >= snapshot_frequency:
        last_snapshot_frame = ot.frame

        # playeraggs is a dict from player to
        #               the aggression snapshot we are assembling now
        playeraggs = dict()
        for player in replay.players:
          playeraggs[player] = [ot.frame, 0, 0, 0, 0, 0]

        for unit, unitloc in trackedunits.items():
            if ot.frame > unit.died_at:
                del trackedunits[unit]
            if ot.frame < unit.died_at and unit.owner is not None and unit.owner in replay.players:
                unitname = unit.name.lower()
                if COUNTS_AS_ARMY.get(unitname):
                  strength = army_strength(replay.expansion, unitname)
                else:
                  strength = 0

                aggression = self.aggressionFor(replay, ot.frame, (unitloc[0], unitloc[1]), unit.owner)
                playeraggs[unit.owner][aggression.value] += strength

        for player in replay.players:
          aggressions[player].append(playeraggs[player])

      trackedunits[ot.obj] = (ot.x, ot.y)

    return aggressions


  def populateBlobWithAggressions(self, blob, replay, ptoi, object_tracks):
    
    # logic for team games isn't right yet, would need to look at all enemy bases
    if len(replay.players) > 2:
      return

    aggressions = self.computeAggressions(replay, object_tracks)

    blob["aggressions"] = dict()
    trackedPlayers = [p for p in replay.players if p in ptoi]
    for player in trackedPlayers:
      blob["aggressions"][ptoi[player]] = aggressions[player]


  def populateBlobFromReplay(self, blob, player, replay, ptoi):
      if player.play_race != 'Zerg':
          return

      if player not in ptoi:
          return

      blobhatches = []

      for hatch in player.macro_hatches.values():
          # how to DRY this up?
          blobhatch = {'first_activity': hatch.finished_at,
                       'last_activity': hatch.died_at,
                       'utilization': hatch.utilization,
                       'inject_time': hatch.inject_time,
                       'active_time': hatch.active_time,
                       'times': hatch.injects}
          blobhatches.append(blobhatch)

      blob["macro"].append([ptoi[player], blobhatches])


  # num_bases is a map from player id to a list of
  # [base_construction_complete, base_destroyed, base_construction_began]
  # frame times for that player's bases.
  #
  # (they are in this weird order for historical backward-compatibility reasons)
  #
  def populateBlobWithNumBases(self, blob, replay, ptoi):

      blob["num_bases"] = list()

      for player in replay.players:
          if player not in ptoi:
              continue
          base_lives = list()
          for base in player.bases:
              if getattr(base, "finished_at", None) != None and getattr(base, 'died_at', None) != None:
                  base_lives.append([base.finished_at, base.died_at, base.started_at])
          blob["num_bases"].append([ptoi[player], base_lives])


  def populateBlobWithScouting(self, blob, replay, ptoi):

      blob["scouting"] = dict()
      for player in replay.players:
          if player not in ptoi:
              continue
          blob["scouting"][ptoi[player]] = player.first_scout_command_frame


  def populateBlobWithUpgrades(self, blob, replay, ptoi):

      blob["upgrades"] = dict()
      for player in replay.players:
          if player not in ptoi:
              continue
          blob["upgrades"][ptoi[player]] = player.upgrades


  def populateBlobWithProtossMacro(self, blob, replay, ptoi):

      blob["pmacro"] = dict()

      for player in replay.players:
          if player not in ptoi:
              continue
          nexus_stats = list()
          for nexus in player.bases:
              if hasattr(nexus, "chronoboosts") and hasattr(nexus, 'maxouts'):
                  nexus_stats.append([nexus.chronoboosts, nexus.maxouts])
          blob["pmacro"][ptoi[player]] = nexus_stats


  def populateBlobWithTerranMacro(self, blob, replay, ptoi):

      blob["tmacro"] = dict()

      for player in replay.players:
          if player not in ptoi:
              continue
          base_stats = list()
          for base in player.bases:
              if hasattr(base, "mules") and hasattr(base, 'maxouts'):
                  base_stats.append([base.mules, base.supplydrops, base.scans, base.maxouts])
          blob["tmacro"][ptoi[player]] = base_stats


  def getOrCreateReplayDB(self, replay, hash, matchDB):
    def createReplay(replay, hash, matchDB):
      replayDB = Replay(
        match = matchDB,
        duration_seconds=replay.length.seconds,
        uploaded_at=datetime.now(),
        processed_at=datetime.now(),
        md5=hash
      )
      replayDB.save()
      return replayDB

    replayDBs = list(Replay.objects.raw("""
      SELECT DISTINCT r.*
      FROM esdb_sc2_match_replays r
      WHERE '{hash}' = md5
      """.format(hash = hash)
    ))

    # Create a new one if we don't find one
    if len(replayDBs) == 0:
        return createReplay(replay, hash, matchDB)

    if len(replayDBs) == 1:
        theReplay = replayDBs[0]
        if theReplay.match is None:
            # this case isnt supposed to happen, but we'll gracefully
            # repair the DB if it does.
            theReplay.match = matchDB
        elif theReplay.match != matchDB:
            # this is seriously not supposed to happen.
            print "Ouch, we used to associate replay {} with match {}, and now we're switching the replay to be associated with match {}".format(theReplay.id, theReplay.match.id, matchDB)
            theReplay.match = matchDB

        theReplay.processed_at = datetime.now()
        theReplay.save()
        return theReplay
    else:
      # TODO multiple replays with the same md5,
      # how did they slip int our DB?! What do we do?!
      print "Oooh, more than one replay found with this md5. Replay IDs:"
      print ",".join(str(replayDB.id) for replayDB in replayDBs)
      return replayDBs[0]

  # returns the match with the played_at closest to the given starttime
  def matchClosestToStartTime(self, matchDBs, starttime):
      result = matchDBs[0]
      distance = abs((starttime - result.played_at).total_seconds())
      for matchDB in matchDBs[1:]:
          newDistance = abs((starttime - matchDB.played_at).total_seconds())
          if newDistance < distance:
              distance = newDistance
              result = matchDB
      return result


  # returns a set of the bnet_ids the played in the given replay
  def getBnetIDSetForReplay(self, replay):
      result = set()
      for player in replay.players:
          if player.toon_id > 0:
              result.add(player.toon_id)
      return result

  def getBnetIDSetForMatchDB(self, matchDB):
      result = set()
      for entity in matchDB.entity_set.all():
          for identity in entity.identities.all():
              if identity.bnet_id > 0:
                  result.add(identity.bnet_id)
      return result

  # return the Match object and a boolean indicating whether or not it was created
  def getOrCreateMatchWithIDAndStart(self, firstIdentityDB, starttime, gamelength_seconds, bnetIDSet, cobrand):

    # Are there any matches with this player starting at around the same time?
    matchDBs = self.matchesWithIDAndStart(firstIdentityDB, starttime, gamelength_seconds)

    # if any of those matches have the right players, then weve got a
    # match
    for matchDB in matchDBs:
        matchBnetIDs = self.getBnetIDSetForMatchDB(matchDB)
        #print "matchBnetIDs: {}, bnetIDSset: {}".format(matchBnetIDs, bnetIDSet)
        if matchBnetIDs == bnetIDSet:
            return matchDB, False

    # If not, create it and be done.
    match = Match()
    match.cobrand = cobrand
    match.save()
    return match, True


  # find any matches that had the given player and started within 3
  # minutes of the given unlocalized UTC time
  def matchesWithIDAndStart(self, firstIdentityDB, starttime, gamelength_seconds):
      rawSQL = """
          SELECT DISTINCT m.*
          FROM esdb_matches m
            JOIN esdb_sc2_match_entities e ON m.id = e.match_id
            JOIN esdb_identity_entities ie ON e.id = ie.entity_id
          WHERE {id} = ie.identity_id
            AND played_at BETWEEN
                     timestampadd(SECOND, -{tol_secs}, '{starttime}') and
                     timestampadd(SECOND, +{tol_secs}, '{starttime}')
          """.format(
                  starttime=starttime.strftime('%Y-%m-%d %H:%M:%S'),
                  tol_secs=180.0,
                  id=firstIdentityDB.id
                  )
      matchDBs = list(Match.objects.raw(rawSQL))

      return matchDBs


  def writeMinimapToS3(self, replayMap, bucket, maphash):
      # extract image
      mapsio = StringIO.StringIO(replayMap.minimap)
      im = Image.open(mapsio)
      cropped = im.crop(im.getbbox())
      cropsize = cropped.size

      # resize height to MAPHEIGHT, and compute new width that
      # would preserve aspect ratio
      minimap_image_width = int(cropsize[0] * (float(MAPHEIGHT) / cropsize[1]))
      finalsize = (minimap_image_width, MAPHEIGHT)
      resized = cropped.resize(finalsize, Image.ANTIALIAS)

      # write cropped resized minimap image to a string as a png
      finalIO = StringIO.StringIO()
      resized.save(finalIO, "png")

      # store that in S3
      k = Key(bucket)
      keystring = "%s_%i.png" % (maphash, MAPHEIGHT)
      k.key = keystring
      k.set_contents_from_string(finalIO.getvalue())

      # clean up
      finalIO.close()


  def getOrCreateMap(self, replay):
      mapDB, created = Map.objects.get_or_create(
          s2ma_hash=replay.map_hash)

      bucket = boto.connect_s3(settings.AWS_ACCESS_KEY_ID,
                               settings.AWS_SECRET_ACCESS_KEY)\
                               .lookup(settings.MINIMAP_BUCKET_NAME)

      if not created:
          k = Key(bucket)
          k.key = "%s_%i.png" % (mapDB.s2ma_hash, 100)
          if not k.exists():
              replay.load_map()
              self.writeMinimapToS3(replay.map, bucket, mapDB.s2ma_hash)
      else:
          replay.load_map()
          self.writeMinimapToS3(replay.map, bucket, replay.map_hash)

          # ggpyjobs#15 - Use the s2ma map name if available in english
          map_name = replay.map.name or replay.map_name
          mapDB.name=map_name
          mapDB.gateway=replay.gateway
          mapDB.save()

      if mapDB.transX is None:
          replay.load_map()

          mapOffsetX, mapOffsetY = replay.map.map_info.camera_left, replay.map.map_info.camera_bottom

          camerarangeX = replay.map.map_info.camera_right - replay.map.map_info.camera_left
          camerarangeY = replay.map.map_info.camera_top - replay.map.map_info.camera_bottom
          camerarange = (camerarangeX,camerarangeY)

          # this is the center of the map, in the SC2 coordinate system
          mapCenter = [mapOffsetX + camerarange[0]/2.0, mapOffsetY + camerarange[1]/2.0]

          # this is the center of the map image, in pixel coordinates
          imageCenter = [50.0 * camerarange[0] / camerarange[1], 50.0]

          # this is the scaling factor to go from the SC2 coordinate
          # system to pixel coordinates
          mapDB.image_scale = 100.0 / camerarange[1]

          # these are the X and Y translations to apply to an SC2
          # camera center coordinate to turn it into the upper-left
          # corner of the camera rectangle in a pixel-based coordinate
          # system in a <canvas> tag, where the upper-left is 0,0.
          mapDB.transX = imageCenter[0] - mapDB.image_scale * (mapCenter[0] + 12.5)
          mapDB.transY = imageCenter[1] + mapDB.image_scale * (mapCenter[1] - 7.5)

          mapDB.save()

      return mapDB

  # return the Match object and a boolean indicating whether or not it was created
  def getOrCreateMatchDB(self, replay, cobrand):

    # Is this match already in our DB? First, look for the player in our DB
    # TODO what if player 0 is an AI?!

    firstIdentityDB = self.getOrCreateIdentity(replay.players[0], replay.start_time, replay.gateway, False)

    # If we dont have the player, then we can't have the match. Just
    # create it and be done.
    if not firstIdentityDB:
        match = Match()
        match.cobrand = cobrand
        match.save()
        return match, True

    bnetIDSet = self.getBnetIDSetForReplay(replay)
    matchDB, created = self.getOrCreateMatchWithIDAndStart(firstIdentityDB, replay.start_time, replay.game_length.seconds, bnetIDSet, cobrand)

    return matchDB, created


  def populateMatchFromReplay(self, replay, matchDB):

      mapDB = self.getOrCreateMap(replay)
      matchDB.map = mapDB
      matchDB.release_string = replay.release_string
      matchDB.played_at = replay.start_time

      # games played in the future are just not to be believed, but we
      # regularly get them.  we'll just amend it to be played now.
      if matchDB.played_at > datetime.now():
          matchDB.played_at = datetime.now()

      matchDB.winning_team = getattr(replay.winner, 'number', 0)
      matchDB.game_type = replay.real_type
      matchDB.category = replay.category
      matchDB.duration_seconds = replay.length.seconds
      matchDB.expansion = 1 if replay.expansion == 'HotS' else 0
      matchDB.gateway = normalize_gateway(replay.gateway)

      # highest_league is 8 for unranked matches.  so if none of the
      # players have highest_league of 8, we call it a ranked match
      matchDB.ranked = len([player.highest_league for player in replay.humans if player.highest_league == 8]) == 0

      matchDB.vs_ai = len([player for player in replay.players if not player.is_human]) > 0

      matchDB.save()



  def getOrCreateIdentity(self, player, played_at, gateway, increment_identity_counters):
    """ given an sc2reader player object, return the corresponding Identity
        object, creating it if necessary.  Also, rename the Identity if
        the replay has a different name for the player than whats in the DB.
        Also, increment the matches_count, seconds_played_sum and avg_apm if instructed to do so.

        Throws Identity.MultipleObjectsReturned error if multiple matching ids found
    """

    # the identity's gateway will be the player's gateway, unless the
    # player has no gateway (so far this is known to happen only with
    # computer players), in which case we use the replay's gateway
    if player.gateway is not None and player.gateway.strip() != '':
        gateway = player.gateway

    #
    # In order to have multiple processes simultaneously parsing and persisting,
    # we must have uniqueness at the DB level, and we must call get_or_create()
    #
    # http://stackoverflow.com/questions/6416213/is-get-or-create-thread-safe/9400486#9400486
    #
    idDB, created = Identity.objects.get_or_create(
        gateway=gateway,
        bnet_id=player.toon_id,
        subregion=player.subregion)


    # remove clan or group tags from the name
    p = re.compile( '\[.*\]' )

    # Update the player's name from this replay if we dont have a name
    # for this player, or the replay is newer than our name
    # information
    change_happened = False

    if not idDB.name or played_at > idDB.name_valid_at:
        newname = p.sub('', player.name)
        if idDB.name != newname:
            idDB.name = newname
            change_happened = True

        if idDB.name_source != 'replay':
            idDB.name_source = 'replay'
            change_happened = True

        if (idDB.name_valid_at is None or (played_at - idDB.name_valid_at).total_seconds() > 3600):
            idDB.name_valid_at = played_at
            change_happened = True

    if increment_identity_counters:
      idDB.matches_count = F('matches_count') + 1
      idDB.seconds_played_sum = F('seconds_played_sum') + player.seconds_played
      idDB.avg_apm = (F('avg_apm') * F('matches_count') + player.avg_apm) / (F('matches_count') + 1)
      change_happened = True

    idDB.type='ESDB::Sc2::Identity'

    # dont bother to generate all this DB traffic for AI identities
    if idDB.bnet_id != 0 and change_happened:
        idDB.save()

    return idDB

  def didPlayerWin(self, player):
    if player.result == "Win":
      return True
    elif player.result == "Loss":
      return False
    else:
      return None

  # also populates per-minute data for the entity
  @transaction.commit_on_success
  def populateEntityFromReplay(self, entityDB, matchDB, player, replay):
    entityDB.team=player.team.number
    entityDB.chosen_race=player.pick_race[0]
    entityDB.race=player.play_race[0]
    entityDB.win=self.didPlayerWin(player)
    entityDB.color=player.color.hex

    if hasattr(player, "avg_apm"):
        entityDB.apm = player.avg_apm

    if hasattr(player, "race_macro"):
        entityDB.race_macro = player.race_macro

    if hasattr(player, "wwpm"):
        entityDB.wpm = sum(player.wwpm.values()) / (replay.length.seconds / 60.0)

    if hasattr(player, "max_creep_spread"):
      if player.max_creep_spread != 0:
        entityDB.max_creep_spread = player.max_creep_spread[1]

    ta = player.total_army
    for unitnum in range(0, MAX_NUM_UNITS):
      setattr(entityDB, "u%(unitnum)i" % {"unitnum": unitnum}, ta[unitnum])

    entityDB.save()

    # The first minute will always be empty due to rounding
    abm = player.army_by_minute
    for minute, counts in list(enumerate(abm))[1:]:
      minuteDB, created = Minute.objects.get_or_create(entity=entityDB, minute=minute)
      for unitnum in range(0, MAX_NUM_UNITS):
        setattr(minuteDB, "u"+str(unitnum), counts[unitnum])
      if hasattr(player, "wwpm"):
        minuteDB.wpm = player.wwpm.get(minute, 0)
      if hasattr(player, "apm"):
        minuteDB.apm = player.apm.get(minute, 0)
      minuteDB.armystrength = player.armystrength_by_minute[minute]
      if hasattr(player, "creep_spread_by_minute"):
        if len(player.creep_spread_by_minute) > 0:
          max_creep_seconds = max([cseconds for cseconds in player.creep_spread_by_minute.keys() if cseconds < minute * 60])
          minuteDB.creep_spread = player.creep_spread_by_minute[max_creep_seconds]
      minuteDB.save()

  def processSummary(self, summarydata, hash):
      """main entry point for s2gs processing."""
      summary = ggfactory.load_game_summary(summarydata)

      matchSummaryDB = self.getMatchSummaryDB(summary, hash)

      try:
          self.populateDBFromSummary(summary, matchSummaryDB)
      except Exception as e:
          if summary.settings['Game Mode'] == 'Automated Match Making':
              raise
          else:
              tb = traceback.format_exc()
              exc_type, exc_obj, exc_tb = sys.exc_info()
              print "Problem with s2gs file for a non-Ladder match, hash {}.  No big deal.  Exception={}. {} {} {}".format(hash, e, exc_type, exc_tb.tb_lineno, tb)
              return None

      assert matchSummaryDB is not None
      assert matchSummaryDB.match is not None
      print "processSummary done. matchSummary {}, match {}".format(matchSummaryDB.id, matchSummaryDB.match.id)

      return matchSummaryDB


  def getMatchSummaryDB(self, summary, hash):
      matchSummaryDB = MatchSummary.objects.get(
          s2gs_hash__exact=hash
      )
      return matchSummaryDB

  def startTime(self, summary):
      return datetime.utcfromtimestamp(summary.time - summary.real_length.seconds)

  def getBlizIDsAndPlayers(self, summary):
      result = list()
      for player in summary.players:
          if not player.is_ai:
              #
              # In order to have multiple processes simultaneously parsing and persisting,
              # we must have uniqueness at the DB level, and we must call get_or_create()
              #
              # http://stackoverflow.com/questions/6416213/is-get-or-create-thread-safe/9400486#9400486
              #
              blizID, created = Identity.objects.get_or_create(
                  gateway=normalize_gateway(summary.gateway),
                  bnet_id=player.bnetid,
                  subregion=player.subregion)
              blizID.type='ESDB::Sc2::Identity'
              blizID.save()
              result.append([blizID, player])
      return result

  def getOrCreateEntity(self, matchDB, blizID):
      entitiesDB = Entity.objects.filter(match=matchDB)
      entitiesDB = entitiesDB.filter(identities=blizID)

      if entitiesDB.count() > 1:
          print "oh crap"
          for entityDB in entitiesDB:
              print entityDB.__dict__
      assert entitiesDB.count() <= 1

      if entitiesDB.count() == 1:
          # TODO check that details are what we expect, and throw exception otherwise?!
          return entitiesDB[0]
      else:
          entityDB = Entity(match=matchDB)
          entityDB.save()
          ie = IdentityEntity(identity=blizID,
                              entity=entityDB)
          ie.save()

      return entityDB

  def populateEntityFromPlayerSummary(self, entityDB, player):
      entityDB.team=player.team.number
      entityDB.race=player.play_race[0]
      entityDB.chosen_race=player.pick_race[0]
      entityDB.win=player.is_winner
      entityDB.color=player.color.hex
      entityDB.save()


  def deletePlayerSummaryFor(self, entityDB, player):
      PlayerSummary.objects.filter(entity=entityDB).delete()

  def deleteEntityStatsFor(self, entityDB, player):
      EntityStats.objects.filter(entity=entityDB).delete()

  def saveBuildOrder(self, boDB, build_order):
      if build_order is None:
          return None

      for boitem in build_order:
          itemDB, created = Item.objects.get_or_create(name=boitem.order)
          boitemDB = BuildOrderItem(build_order=boDB,
                                    item=itemDB,
                                    build_seconds=boitem.time,
                                    supply=boitem.supply,
                                    total_supply=boitem.total_supply)
          boitemDB.save()

  def saveGraph(self, graphDB, graph):
      for time,value in graph.as_points():
          gpDB = GraphPoint(graph=graphDB,
                            graph_seconds=time,
                            graph_value=value)
          gpDB.save()

  def createPlayerSummaryFromReplay(self, entityDB, player):

      psDB = PlayerSummary(entity=entityDB,
                           build_order=None, army_graph=None, income_graph=None,
                           resources=None,
                           units=None,
                           structures=None,
                           overview=None,
                           average_unspent_resources=player.average_unspent_resources,
                           resource_collection_rate=player.average_resource_collection_rate,
                           workers_created=player.workers_created,
                           units_trained=player.units_trained,
                           killed_unit_count=player.units_killed,
                           structures_built=player.structures_built,
                           structures_razed_count=player.structures_razed)
      psDB.enemies_destroyed = None
      psDB.time_supply_capped = None
      psDB.idle_production_time = None
      psDB.resources_spent = None
      psDB.apm = None

      psDB.save()

      return psDB

  def createPlayerSummaryFor(self, entityDB, player):

      psDB = PlayerSummary(entity=entityDB,
                           build_order=None, army_graph=None, income_graph=None,
                           resources=player.resource_score,
                           units=player.unit_score,
                           structures=player.structure_score,
                           overview=player.overview_score,
                           average_unspent_resources=player.avg_unspent_resources,
                           resource_collection_rate=player.resource_collection_rate,
                           workers_created=player.workers_created,
                           units_trained=player.units_trained,
                           killed_unit_count=player.units_killed,
                           structures_built=player.structures_built,
                           structures_razed_count=player.structures_razed)
      psDB.enemies_destroyed = player.enemies_destroyed
      psDB.time_supply_capped = player.time_supply_capped
      psDB.idle_production_time = player.idle_production_time
      psDB.resources_spent = player.resources_spent
      psDB.apm = player.apm

      psDB.save()

      return psDB

  def winningTeam(self, summary):
      for player in summary.players:
          if player.is_winner:
              return player.team.number
      return None


  def category(self, summary):
      if summary.settings['Game Mode'] == 'Automated Match Making':
        return 'Ladder'

      return summary.settings['Game Mode']


  def updateMatchWithSummary(self, matchDB, summary):
      # the start and duration from the s2gs are the most reliable
      # source for this information, better than the replays.
      matchDB.duration_seconds = summary.game_length.seconds
      matchDB.played_at = summary.start_time
      matchDB.expansion = 1 if summary.expansion == 'HotS' else 0

      # game_type, category and winning_team are currently fine from the replays,
      # so we won't overwrite those.
      if matchDB.game_type is None or len(matchDB.game_type) == 0:
          matchDB.game_type = summary.real_type

      if matchDB.category is None or len(matchDB.category) == 0:
          matchDB.category = self.category(summary)

      if matchDB.winning_team is None:
          matchDB.winning_team = self.winningTeam(summary)

      matchDB.save()


  def populateDBFromSummary(self, summary, matchSummaryDB):

      biaps = self.getBlizIDsAndPlayers(summary)
      bnetIDSet = set([blizID.bnet_id for [blizID, player] in biaps])
      matchDB, created = self.getOrCreateMatchWithIDAndStart(biaps[0][0], summary.start_time, summary.game_length.seconds, bnetIDSet, None)

      self.updateMatchWithSummary(matchDB, summary)
      mapfactsDB, created = MapFacts.objects.get_or_create(map_name=summary.map_name,
                                                           map_description=summary.map_description,
                                                           map_tileset=summary.map_tileset)
      matchSummaryDB.mapfacts = mapfactsDB
      matchSummaryDB.match = matchDB
      matchSummaryDB.save()

      for [blizID, player] in biaps:
          entityDB = self.getOrCreateEntity(matchDB, blizID)
          self.populateEntityFromPlayerSummary(entityDB, player)
          self.deletePlayerSummaryFor(entityDB, player)
          self.createPlayerSummaryFor(entityDB, player)

      matchSummaryDB.processed_at = datetime.now()
      matchSummaryDB.save()

      return None


  # bases is a list of [construction_complete, base_destroyed, construction_began] frame times for the bases
  # (they are in this weird order for historical backward-compatibility reasons)
  #
  # returns a list of [frame, num_bases] values, indicating how
  # many bases the player had at that time.
  #
  def compute_base_xy(self, basetimes):
    flat_basetimes = [item for sublist in basetimes for item in sublist[0:2]]
    unique_sorted_basetimes = sorted(list(set(flat_basetimes)))
    bases_alive_at_time = list()
    for time in unique_sorted_basetimes:
      num_bases_alive = len([base for base in basetimes if time >= base[0] and time <= base[1]])
      bases_alive_at_time.append(num_bases_alive)
    return zip(unique_sorted_basetimes, bases_alive_at_time)

  def base_benchmarks(self, basetimes):
    base_xy = self.compute_base_xy(basetimes)
    answer = [-1, -1]
    two_base_times = [xy[0] for xy in base_xy if xy[1] == 2]
    three_base_times = [xy[0] for xy in base_xy if xy[1] == 3]
    if len(two_base_times) > 0:
      answer[0] = two_base_times[0] / 16
    if len(three_base_times) > 0:
      answer[1] = three_base_times[0] / 16
    return answer


  def createEntityStatsFor(self, entityDB, player, highest_leagues, matchblob, identity_id):

    one_mineral_income = 640
    one_gas_income = 228
    one_income = one_mineral_income + one_gas_income

    esDB = EntityStats(entity=entityDB,
                       highest_league=(highest_leagues[player.uid] - 1))

    income_times = [-1, -1, -1]
    mineral_income_times = [-1, -1, -1]
    gas_income_times = [-1, -1, -1]
    worker22_times = [-1, -1, -1]

    income_pair = zip(matchblob['MineralsCollectionRate'][identity_id], matchblob['VespeneCollectionRate'][identity_id])
    for idx, pair in enumerate(income_pair):
      income = int(pair[0]) + int(pair[1])
      for benchmark in [0,1,2]:
        if (income_times[benchmark] == -1) and (income >= (benchmark + 1) * one_income):
          income_times[benchmark] = idx * 10
        if (mineral_income_times[benchmark] == -1) and (int(pair[0]) >= (benchmark + 1) * one_mineral_income):
          mineral_income_times[benchmark] = idx * 10
        if (gas_income_times[benchmark] == -1) and (int(pair[1]) >= (benchmark + 1) * one_gas_income):
          gas_income_times[benchmark] = idx * 10
        if (worker22_times[benchmark] == -1) and (int(matchblob['WorkersActiveCount'][identity_id][idx]) >= (benchmark + 1) * 22):
          worker22_times[benchmark] = idx * 10

    thebasetimes = [baseinfo[1] for baseinfo in matchblob['num_bases'] if int(baseinfo[0]) == int(identity_id)][0]
    base_timings = self.base_benchmarks(thebasetimes)

    miningbase_timings = [-1, -1]
    if hasattr(player, 'miningbases'):
      for idx, miningbasepair in enumerate(player.miningbases[0:2]):
        miningbase_timings[idx] = miningbasepair[1] / 16

    for benchmark in [0,1,2]:
      if income_times[benchmark] != -1:
        setattr(esDB, "saturation_{}".format(benchmark+1), income_times[benchmark])
      if mineral_income_times[benchmark] != -1:
        setattr(esDB, "mineral_saturation_{}".format(benchmark+1), mineral_income_times[benchmark])
      if gas_income_times[benchmark] != -1:
        setattr(esDB, "gas_saturation_{}".format(benchmark+1), gas_income_times[benchmark])
      if worker22_times[benchmark] != -1:
        setattr(esDB, "worker22x_{}".format(benchmark+1), worker22_times[benchmark])

    for benchmark in [0,1]:
      if base_timings[benchmark] != -1:
        setattr(esDB, "base_{}".format(benchmark+2), base_timings[benchmark])
      if miningbase_timings[benchmark] != -1:
        setattr(esDB, "miningbase_{}".format(benchmark+2), miningbase_timings[benchmark])

    esDB.save()


  def reprocessEntityStatsForAllPlayers(self, replay, blob):
    matchDB, created = self.getOrCreateMatchDB(replay, None)
    playerToIdentityId = {}

    highest_leagues = [player.highest_league for player in replay.humans]

    for player in replay.players:
      idDB = self.getOrCreateIdentity(player, replay.start_time, replay.gateway, False)
      entityDB = self.getOrCreateEntity(matchDB, idDB)
      if player.toon_id > 0:
        playerToIdentityId[player] = idDB.id

      if replay.build >= 25446 and player.toon_id > 0:
        self.deleteEntityStatsFor(entityDB, player)
        self.createEntityStatsFor(entityDB, player, highest_leagues, blob, playerToIdentityId[player])
