import re, math, itertools
from collections import defaultdict, deque
from sc2reader.events import *
from sc2reader.utils import DepotFile
from sc2reader.factories.plugins.utils import plugin
from pprint import pprint
from xml.dom import minidom

def framestr(frame):
    if frame is None:
        return 'None'
    return str(Length(seconds=frame/16)) + '.' + str(frame % 16)

def get_unit_type(unit):
    is_building = unit.is_building and 'Crawler' not in unit.name # Crawlers are like units
    if unit.name in ('Overseer','BroodLord','Ravager','Lurker') or is_building: # Overseers,BroodLords,Ravagers and Lurkers morph but they are their own units
        unit_type = unit.name.lower()
    elif unit.name in ('Viking','VikingAssault'):
        unit_type = 'viking'
    elif unit.name in ('Hellion','BattleHellion'):
        unit_type = 'hellion'
    else:
      #print hex(unit.id), unit.name, "->", unit.type_history.values()[0].name.lower()
      if len(unit.type_history.values()) > 0:
        unit_type = unit.type_history.values()[0].name.lower()
      else:
        unit_type = None

    return unit_type

# TODO: Once the sc2reader:new_data branch is finished we won't need this.
# Include buildings for ownership tracking but don't include them in army tracking
unit_data = {'WoL':
   {'Protoss':[
    (False,'probe', [50,0,1]),
    (True,'zealot', [100,0,2]),
    (True,'sentry', [50,100,2]),
    (True,'stalker', [125,50,2]),
    (True,'hightemplar', [50,150,2]),
    (True,'darktemplar', [125,125,2]),
    (True,'immortal', [250,100,4]),
    (True,'colossus', [300,200,6]),
    (True,'archon', [175,275,4]), # Can't know the cost, split the difference.
    (True,'observer', [25,75,1]),
    (True,'warpprism', [200,0,2]),
    (True,'phoenix', [150,100,2]),
    (True,'voidray', [250,150,3]),
    (True,'carrier', [350,250,6]),
    (True,'mothership', [400,400,8]),
    (True,'photoncannon', [150,0,0]),
    #(True,'interceptor', [25,0,0]), # This is technically a army unit

],'Terran':[
    (False,'scv', [50,0,1]),
    (True,'marine', [50,0,1]),
    (True,'marauder', [100,25,2]),
    (True,'reaper', [50,50,2]),
    (True,'ghost', [200,100,2]),
    (True,'hellion', [100,0,2]),
    (True,'siegetank', [150,125,2]),
    (True,'thor', [300,200,6]),
    (True,'viking', [150,75,2]),
    (True,'medivac', [100,100,2]),
    (True,'banshee', [150,100,3]),
    (True,'raven', [100,200,2]),
    (True,'battlecruiser', [400,300,6]),
    (True,'planetaryfortress', [150,150,0]),
    (True,'missileturret', [100,0,0]),

],'Zerg':[
    # Cumulative costs, including drone costs
    (False,'drone', [50,0,1]),   #0
    (True,'zergling', [25,0,.5]),
    (True,'queen', [150,0,2]),
    (True,'baneling', [50,25,.5]),
    (True,'roach', [75,25,2]),
    (False,'overlord', [100,0,0]), #5
    (True,'overseer', [50,50,0]),       # dont include the overlord cost
    (True,'hydralisk', [100,50,2]),
    (True,'spinecrawler', [150,0,0]),
    (True,'sporecrawler', [125,0,0]),
    (True,'mutalisk', [100,100,2]), #10
    (True,'corruptor', [150,100,2]),
    (True,'broodlord', [300,250,4]),
    (True,'broodling', [0,0,0]),
    (True,'infestor', [100,150,2]),
    (True,'infestedterran', [0,0,0]),
    (True,'ultralisk', [300,200,6]),
    (False,'nydusworm', [100,100,0]),
]},
'HotS':    {'Protoss':[
    (False,'probe', [50,0,1]),
    (True,'zealot', [100,0,2]),
    (True,'sentry', [50,100,2]),
    (True,'stalker', [125,50,2]),
    (True,'hightemplar', [50,150,2]),
    (True,'darktemplar', [125,125,2]),   #5
    (True,'immortal', [250,100,4]),
    (True,'colossus', [300,200,6]),
    (True,'archon', [175,275,4]), # Can't know the cost, split the difference.
    (True,'observer', [25,75,1]),
    (True,'warpprism', [200,0,2]),       #10
    (True,'phoenix', [150,100,2]),
    (True,'voidray', [250,150,4]),
    (True,'carrier', [350,250,6]),
    (True,'mothership', [400,400,8]),  # includes mothershipcore cost
    (True,'photoncannon', [150,0,0]),    #15
    (True,'oracle', [150,150,3]),
    (True,'tempest', [300,200,4]),
    (True,'mothershipcore', [100,100,2]),
    #(True,'interceptor', [25,0,0]), # This is technically a army unit

],'Terran':[
    (False,'scv', [50,0,1]), #0
    (True,'marine', [50,0,1]),
    (True,'marauder', [100,25,2]),
    (True,'reaper', [50,50,1]),
    (True,'ghost', [200,100,2]),
    (True,'hellion', [100,0,2]), #5
    (True,'siegetank', [150,125,2]),
    (True,'thor', [300,200,6]),
    (True,'viking', [150,75,2]),
    (True,'medivac', [100,100,2]),
    (True,'banshee', [150,100,3]),# 10
    (True,'raven', [100,200,2]),
    (True,'battlecruiser', [400,300,6]),
    (True,'planetaryfortress', [150,150,0]),
    (True,'missileturret', [100,0,0]),
    (True,'widowmine', [75,25,2]), #15

],'Zerg':[
    # Cumulative costs, including drone costs
    (False,'drone', [50,0,1]),
    (True,'zergling', [25,0,.5]),
    (True,'queen', [150,0,2]),
    (True,'baneling', [50,25,.5]),
    (True,'roach', [75,25,2]),
    (False,'overlord', [100,0,0]),
    (True,'overseer', [50,50,0]),       # dont include the overlord cost because we arent including costs of pylons or supply depots
    (True,'hydralisk', [100,50,2]),
    (True,'spinecrawler', [150,0,0]),
    (True,'sporecrawler', [125,0,0]),
    (True,'mutalisk', [100,100,2]),
    (True,'corruptor', [150,100,2]),
    (True,'broodlord', [300,250,4]),
    (True,'broodling', [0,0,0]),
    (True,'infestor', [100,150,2]),
    (True,'infestedterran', [0,0,0]),
    (True,'ultralisk', [300,200,6]),
    (False,'nydusworm', [100,100,0]),
    (True,'swarmhost', [200,100,3]),
    (True,'viper', [100,200,3]),

]},
'LotV':    {'Protoss':[
    (False,'probe', [50,0,1]),
    (True,'zealot', [100,0,2]),
    (True,'sentry', [50,100,2]),
    (True,'stalker', [125,50,2]),
    (True,'hightemplar', [50,150,2]),
    (True,'darktemplar', [125,125,2]),   #5
    (True,'immortal', [250,100,4]),
    (True,'colossus', [300,200,6]),
    (True,'archon', [175,275,4]), # Can't know the cost, split the difference.
    (True,'observer', [25,75,1]),
    (True,'warpprism', [200,0,2]),       #10
    (True,'phoenix', [150,100,2]),
    (True,'voidray', [250,150,4]),
    (True,'carrier', [350,250,6]),
    (True,'mothership', [400,400,8]),  # includes mothershipcore cost
    (True,'photoncannon', [150,0,0]),    #15
    (True,'oracle', [150,150,3]),
    (True,'tempest', [300,200,4]),
    (True,'mothershipcore', [100,100,2]),
    (True,'disruptor', [100,100,2]),
    (True,'adept', [100,25,2]),          #20
    #(True,'interceptor', [25,0,0]), # This is technically a army unit

],'Terran':[
    (False,'scv', [50,0,1]), #0
    (True,'marine', [50,0,1]),
    (True,'marauder', [100,25,2]),
    (True,'reaper', [50,50,1]),
    (True,'ghost', [200,100,2]),
    (True,'hellion', [100,0,2]), #5
    (True,'siegetank', [150,125,2]),
    (True,'thor', [300,200,6]),
    (True,'viking', [150,75,2]),
    (True,'medivac', [100,100,2]),
    (True,'banshee', [150,100,3]),# 10
    (True,'raven', [100,200,2]),
    (True,'battlecruiser', [400,300,6]),
    (True,'planetaryfortress', [150,150,0]),
    (True,'missileturret', [100,0,0]),
    (True,'widowmine', [75,25,2]), #15
    (True,'cyclone', [150,150,3]),
    (True,'liberator', [150,150,3]),

],'Zerg':[
    # Cumulative costs, including drone costs
    (False,'drone', [50,0,1]), #0
    (True,'zergling', [25,0,.5]),
    (True,'queen', [150,0,2]),
    (True,'baneling', [50,25,.5]),
    (True,'roach', [75,25,2]),
    (False,'overlord', [100,0,0]), #5
    (True,'overseer', [50,50,0]),       # dont include the overlord cost because we arent including costs of pylons or supply depots
    (True,'hydralisk', [100,50,2]),
    (True,'spinecrawler', [150,0,0]),
    (True,'sporecrawler', [125,0,0]),
    (True,'mutalisk', [100,100,2]), #10
    (True,'corruptor', [150,100,2]),
    (True,'broodlord', [300,250,4]),
    (True,'broodling', [0,0,0]),
    (True,'infestor', [100,150,2]),
    (True,'infestedterran', [0,0,0]), #15
    (True,'ultralisk', [300,200,6]),
    (False,'nydusworm', [100,100,0]),
    (True,'swarmhost', [200,100,3]),
    (True,'viper', [100,200,3]),
    (True,'lurker', [150,150,3]), #20
    (True,'ravager', [100,100,3]),
]}}


ARMY_MAP, ARMY_INFO, COUNTS_AS_ARMY, UNITS  = {}, {}, {}, {}
MAX_NUM_UNITS = 0
for expansion, expansion_data in unit_data.items():
    ARMY_INFO[expansion] = {}
    for race, unit_list in expansion_data.items():
        if len(unit_list) > MAX_NUM_UNITS:
            MAX_NUM_UNITS = len(unit_list)
        if race not in UNITS:
            UNITS[race] = list()
        for index, (army, name, info) in enumerate(unit_list):
            ARMY_INFO[expansion][name] = info
            if name not in UNITS[race]:
                UNITS[race].append(name)
                ARMY_MAP[name] = index
                COUNTS_AS_ARMY[name] = army

#
# computes the minerals + gas strength of the unit 'name' for the given expansion
#
# this is a little ugly, but no point in making it pretty since "Once the
# sc2reader:new_data branch is finished we won't need this."
#
def army_strength(expansion, name):
    info = ARMY_INFO[expansion][name]
    return info[0] + info[1]


@plugin
def WWPMTracker(replay, ww_length_frames, workers=set(["TrainProbe", "MorphDrone", "TrainDrone", "TrainSCV"])):
    """ Implements:
            player.wwpm = dict[minute] = count

            Where distict waves are counted by ignoring all train commands for
            ww_length_frames frames after the inital train command.

        Requires: None
    """
    # Tracker only needed for pre-2.0.8 replays
    if replay.build >= 25446: return replay

    efilter = lambda e: isinstance(e, BasicCommandEvent) and e.ability_name in workers
    for player in replay.players:
        player.wwpm = defaultdict(int)
        last_worker_built = -ww_length_frames
        for event in filter(efilter, player.events):
            if (event.frame - last_worker_built) > ww_length_frames:
                last_worker_built = event.frame
                event.player.wwpm[event.second/60] += 1

    return replay

@plugin
def ActivityTracker(replay):
    """ Implements:
            obj.first_activity = framestamp
            obj.last_activity = framestamp

            Where obj includes all objects including critters, resources, and
            neutral buildings (Xel'Naga) and activity is defined as any time
            the unit is selected by any person (players and observers) or the
            is the target of an ability.

        Requires: SelectionTracker
    """
    # Tracker only needed for pre-2.0.8 replays
    if replay.build >= 25446: return replay

    # Initialize all objects
    for obj in replay.objects.values():
        obj.first_activity = None
        obj.last_activity = None

    def mark_activity(obj,frame):
        if obj.first_activity == None or obj.first_activity > frame:
            obj.first_activity = frame
        if obj.last_activity == None or obj.last_activity < frame:
            obj.last_activity = frame

    efilter = lambda e: isinstance(e, SelectionEvent) or isinstance(e, GetControlGroupEvent)
    for event in filter(efilter, replay.events):
        # Mark all currently selected units
        for obj in event.selected:
            mark_activity(obj, event.frame)

        # Also mark units that may have been added to a non-active buffer
        if getattr(event,'bank',0xA) != 0x0A:
            for obj in getattr(event,'objects',[]):
                mark_activity(obj, event.frame)

        #Also mark all previously (just before now) selected units
        for obj in event.player.selection[event.frame-1][0x0A].objects:
            mark_activity(obj, event.frame)

    # the last set of units selected is alive till the end
    for person in replay.entities:
        for obj in person.selection[replay.frames][0x0A].objects:
            mark_activity(obj, replay.frames)

    # Mark Ability Target Activity
    efilter = lambda e: isinstance(e, TargetUnitCommandEvent) and e.target
    for event in filter(efilter, replay.events):
        mark_activity(event.target, event.frame)

    return replay


@plugin
def OwnershipTracker(replay):
    """ implements:
            player.units = set(unit objects)
            unit.owner = player object

            where ownership is determined by race for non-mirrored 1v1s and by
            applying a series of game engine constraints for all other cases:

                1) only units you own can be commanded
                2) multi-unit selections can only be of your own units

            these rules break when sharing control in team games, to mitigate
            this ownership can only be set once after which point it is locked.

        requires: selectiontracker
    """
    # Tracker only needed for pre-2.0.8 replays
    if replay.build >= 25446: return replay

    # todo: account for non-player owned (neutral) objects
    # todo: we can possibly mop up a few more units by checking for
    #       any single race player and doing mass assignment. this
    #       could work in ffa, 2v2, etc for a subset of players.
    # todo: we can also use bad owner events + race rules in many team games.

    # initialize all objects
    for unit in replay.objects.values():
        unit.owner = None

    # a race-based analysis is more efficient and effective in 1v1 cases.
    if replay.real_type=='1v1':
        # we can't assume what the pid's will be
        player1 = replay.teams[0].players[0]
        player2 = replay.teams[1].players[0]
        p1_race, p2_race = player1.play_race, player2.play_race

        # if the races are different then ownership is easy
        if p1_race != p2_race:
            p1_units, race1_units = set(), UNITS[p1_race]
            p2_units, race2_units = set(), UNITS[p2_race]
            for obj in replay.objects.values():
                obj_race = getattr(obj, 'race', None)
                if obj_race == p1_race:
                    obj.owner = player1
                    p1_units.add(obj)
                elif obj_race == p2_race:
                    obj.owner = player2
                    p2_units.add(obj)
                else:
                    "must be neutral unit or player unit we don't care about."

            player1.units = p1_units
            player2.units = p2_units
            return replay
    # cut out here if the above conditions applied
    # otherwise do the more complicated logic below

    # only loop over players since no one else can own anything
    for player in replay.players:
        player_units = set()
        player_selection = player.selection
        play_race = player.play_race

        # don't assign ownership to off race units
        # first owner stays owner to keep shared control game events
        # from double counting ownership in team games
        def mark_ownership(objects, player):
            unit_check = lambda obj: obj.owner == None and getattr(obj, 'race', None) == play_race
            for obj in filter(unit_check, objects):
                obj.owner = player
                player_units.add(obj)

        # a player can only select more than one unit at a time when selecting her own units
        # warning: also shared control units, can't detect that though
        efilter = lambda e: isinstance(e, SelectionEvent) or isinstance(e, CommandEvent)
        for event in filter(efilter, player.events):
            current_selection = player_selection[event.frame][0x0A].objects
            if len(current_selection) > 1:
                mark_ownership(current_selection, player)

        # a player can only issue orders to her own units
        # warning: also a shared control unit, can't detect that though
        efilter = lambda e: isinstance(e, BasicCommandEvent)
        for event in filter(efilter, player.events):
            mark_ownership(player_selection[event.frame][0x0A].objects, player)

        player.units = player_units

    return replay

@plugin
def TrainingTracker(replay):
    """ implements:
            player.train_commands = dict[unit_name] = list(framestamps)

            does not attempt to filter out spammed events.

        requires: none
    """
    # Tracker only needed for pre-2.0.8 replays
    if replay.build >= 25446: return replay

    # todo: make an attempt to handle cancels? build building commands can be soft canceled by issue another order en-route.
    # todo: shift clicking to build buildings creates an additional type of queue.
    efilter = lambda e: hasattr(e,'ability') and getattr(e.ability, 'build_unit', None)
    for player in replay.players:
        train_commands = defaultdict(list)
        for event in filter(efilter, player.events):
            train_commands[event.ability.build_unit.name].append(event.frame)
        player.train_commands = train_commands

    return replay

@plugin
def LifeSpanTracker(replay):
    """ implements:
            unit.started_at = framestamp
            unit.finished_at = framestamp
            unit.died_at = framestamp

            where birth is the framestamp of the closest corresponding unit
            build event before the unit's first_activity and death is the
            unit's last_activity point.

            if a prior build event cannot be found then the unit either
                a) is not actually owned by this player or
                b) is a starting unit, apply unit.started_at/finished_at=1 for first frame

        requires: trainingtracker, activitytracker, ownershiptracker
    """
    # Tracker only needed for pre-2.0.8 replays
    if replay.build >= 25446:
        for unit in replay.objects.values():
            if unit.died_at == None:
                unit.died_at = replay.frames
        return replay

    # TODO: Death is obviously taking a very pessimistic view; most units don't
    # die immediately after their last selection...
    for unit in replay.objects.values():
        unit.started_at = unit.first_activity
        unit.finished_at = unit.first_activity
        unit.died_at = unit.last_activity

    # Make a second pass using training information
    for player in replay.players:

        # Make a copy using a reversed deque for performance
        unmatched_train_commands = dict()
        for unit_name, frame_list in player.train_commands.items():
            unmatched_train_commands[unit_name.lower()] = deque(sorted(frame_list,reverse=True))

        # Work through the units from last activity to first activity and match
        # them with the most recent train command. This results in the most
        # conservative guesses on our part.
        zergling_parity = True
        auto_units = set(['broodling','interceptor'])
        start_units = set(['probe','drone','overlord','scv'])
        for unit in sorted(player.units, key=lambda u: (u.finished_at, u), reverse=True):
            name = get_unit_type(unit)
            if name in ARMY_MAP:
                # Find the best guess for a matching train command
                build_time = False
                if name in unmatched_train_commands:
                    # Use the first build_time before the first_activity
                    unit_build_times = unmatched_train_commands[name]
                    while len(unit_build_times) > 0:
                        build_time = unit_build_times.popleft()
                        if build_time <= unit.first_activity:
                            break
                    else:
                        build_time = False

                if build_time:
                    unit.started_at = build_time
                    unit.finished_at = build_time

                    # Zerglings always come in twos so push it back on for the twin
                    if name == 'zergling':
                        zergling_parity = not zergling_parity
                        if not zergling_parity:
                            unit_build_times.appendleft(build_time)

                elif name in start_units:
                    unit.started_at = 1
                    unit.finished_at = 1

                elif name in auto_units:
                    pass

                elif player.is_human:
                    # This is likely to happen with Broodlords, Overseers, and
                    # PlanetaryFortresses because they share lifetime with previous forms
                    print "Bad ownership for {}: {} selected without matching train command".format(player, name)

    return replay


@plugin
def ArmyTracker(replay):
    """ Implements:
            player.total_army = dict[UnitNum] = count
            player.army_by_minute = dict[minute][UnitNum] = count

            Where UnitNum is the ordering number specified in ARMY_MAP and
            army_by_minute count represents the total known to be alive at
            that minute mark of the game.

        Requires: OwnershipTracker, LifeSpanTracker
    """

    # Chop off trailing seconds since we use floor below
    replayMinutesCompleted = replay.frames/960
    for player in replay.players:
        player.total_army = [0] * MAX_NUM_UNITS
        player.army_by_minute = list()
        player.armystrength_by_minute = list()
        for i in range(0, replayMinutesCompleted+1):
            player.army_by_minute.append([0] * MAX_NUM_UNITS)
            player.armystrength_by_minute.append(0)

        for unit in player.units:
            unitname = get_unit_type(unit)
            unitnum = ARMY_MAP.get(unitname, None)
            if unitnum == None or unit.hallucinated:
                continue

            if COUNTS_AS_ARMY.get(unitname):
                unit_army_strength = army_strength(replay.expansion, unitname)
            else:
                unit_army_strength = 0

            player.total_army[unitnum] += 1

            if unit.finished_at == None:
                print "unit missing birth info! {} {} {}".format(unit, unit.finished_at, unit.died_at)
                continue

            if unit.died_at == None:
                unit.died_at = replay.frames

            # This understates the army strength by rounding birth up and death down
            firstMinuteInArmy = int(math.ceil(unit.finished_at/960.0))
            lastMinuteInArmy = unit.died_at/960

            # Mark the unit strength for the whole time range
            for i in range(firstMinuteInArmy, lastMinuteInArmy+1):
                player.army_by_minute[i][unitnum] += 1
                player.armystrength_by_minute[i] += unit_army_strength

    return replay

def sqdist(loc1, loc2):
    return (loc1[0] - loc2[0]) ** 2 + (loc1[1] - loc2[1]) ** 2

def centerOf(loclist):
  centerX = float(sum([loc[0] for loc in loclist])) / len(loclist)
  centerY = float(sum([loc[1] for loc in loclist])) / len(loclist)
  return (centerX, centerY)


# see your journal entry 20130528 for how this value got set
MINING_BASE_MIN_SQ_DIST = 64

debug_miningbases = False
debuglevel_miningbases = 0

def isMiningLoc(mineralLocs, location):
    # on every melee map so far, this has been the limit for the
    # sixth-closest mineral patch from the starting base, in squared
    # distance units.  Its as large as it is due to discretization
    # effects, since locations are reported on a grid 4x coarser than
    # the actual grid units.

    closeMineralLocsAndDists = [(mineralLoc,sqdist(mineralLoc, location)) for mineralLoc in mineralLocs \
                                if sqdist(mineralLoc, location) <= MINING_BASE_MIN_SQ_DIST]

    # debug/research purposes only
    # closeMineralLocsAndDists = sorted(closeMineralLocsAndDists, key=lambda pair: pair[1])

    if len(closeMineralLocsAndDists) < 6:
        return False

    if debug_miningbases and debuglevel_miningbases >= 1:
      closeMineralLocsAndDists = closeMineralLocsAndDists[0:6]
      centroid = centerOf([pair[0] for pair in closeMineralLocsAndDists])
      maxdist = 0
      mindist = 9999
      #      print "centroid is {}".format(centroid)
      mineral_centroid_dists = [sqdist(pair[0], centroid) for pair in closeMineralLocsAndDists]
      mineral_base_dists = [sqdist(pair[0], location) for pair in closeMineralLocsAndDists]
      #      for pair in closeMineralLocsAndDists:
      #        print "mineral {} dist to centroid {}".format(pair[0], sqdist(pair[0], centroid))
      print "base {} dist to centroid {}, min/max mineral/centroid dist {} {}, min/max mineral/base dist {} {}".format(location, int(sqdist(location, centroid)), int(min(mineral_centroid_dists)), int(max(mineral_centroid_dists)), int(min(mineral_base_dists)), int(max(mineral_base_dists)))
      #      print "base {} direction to centroid {}".format(location, (centroid[0] - location[0], centroid[1] - location[1]))

      closeMineralLocsAndDists = sorted(closeMineralLocsAndDists, key=lambda pair: pair[1])
      closeMineralLocsAndDists = closeMineralLocsAndDists
#        print closeMineralLocsAndDists
#    for i in range(0,5):
#        print "internal dist {}".format(sqdist(closeMineralLocsAndDists[i][0], closeMineralLocsAndDists[i+1][0]))

    return True


@plugin
def MapFileDepotFixer(replay):
    # Hacks to handle S2MA files from blizzards private network
    map_hackery = dict()
    map_hackery["http://BN.depot.battle.net:1119/4fc096b0cf4b9e3c8b6c3aafa20297b860dde6501b1c2a785d0c3f9072b2510d.s2ma"] = \
        ['us  ', 'dede4cef85d6b0aa5449f6fec886ecf4e0c5c808662184efbe7bd2307672e783']
    map_hackery["http://BN.depot.battle.net:1119/404d10095b2c5719f2974600a6193525d04bea221d2f0d5ec99172277b41856f.s2ma"] = \
        ['us  ', '0900dd4bfd0776525179f0981e8c88f622661d964aae9a47c1eafd1745c2d1d0']
    map_hackery["http://BN.depot.battle.net:1119/0a51b712d9789f6680d63279091704388253310c4c298b8d411ced5ff58cf21a.s2ma"] = \
        ['us  ', '459a7b8a6a86e511ec7fd27b340d0170a9f6021cdd8a29273a7944e44157fc85']
    map_hackery["http://BN.depot.battle.net:1119/6acf3476786c6a8e0b2647a1af6ff37f4423b8e2c6b19097e55d2c30777b22f9.s2ma"] = \
        ['us  ', 'cd709b0fc39ef13b4ae45d086c41313db6e01b9c7c84e439b061398bfc31a266']
    map_hackery["http://BN.depot.battle.net:1119/ea3f0c51bb96030120e39ddb65920f8f3e3f37705d1b67307953d46440945357.s2ma"] = \
        ['us  ', '25be8e8dfd468d97a7e7c0580ce94488b082ba6b3241dba692f38c0743cede21']
    map_hackery["http://BN.depot.battle.net:1119/2cdab4966a73a4cf4377c5171e0e2b1878bfc753de10ee43d3c9d2fe4868a6a2.s2ma"] = \
        ['us  ', '571da9a6ed7c6582d8a741e76806782c62d6536e0e178f1be592c70ad72c1568']
    map_hackery["http://BN.depot.battle.net:1119/e5305f5d9161bde916eb0cd2ea2ed34ce7202e7c3f16f360360e1c648ccc4d00.s2ma"] = \
        ['eu  ', '49d535dd8010198703ea4b724281ff890ea9502c8d3edc4e212669590ef73051']
    map_hackery["http://BN.depot.battle.net:1119/7154dfaaef2474fdbb058a73641011b2b7ba559bc89b258cc7f92aac919599b5.s2ma"] = \
        ['eu  ', 'c1b6d010c1c8e7adba968e25632ea242380358bcdcffe72fb4a0bb3e4cb514ec']
    map_hackery["http://BN.depot.battle.net:1119/ddd8ed3e84b9317f73b0d9606892b5207fe41b7c3a668b642a65464c5f1148b1.s2ma"] = \
        ['us  ', '0fd5580b3451b5eebea4274a85dc96a881613807f2e0d665bddef430ae6c1363']
    map_hackery["http://BN.depot.battle.net:1119/168de43e37ad4a8c59502c5e0563781b73b1e910ace1c5981f40cdd16c0d4805.s2ma"] = \
        ['us  ', 'bd257b57b7ba66ee91bec88ac3962f20a65006b547012fd396737185ce5df5f3']
    map_hackery["http://BN.depot.battle.net:1119/eba3e8a813000fc0b2daec028d9d1b7b277134afb3f7678edf2e8a53d97df34e.s2ma"] = \
        ['us  ', '4fc6e2546ea17fea0b0c9eaaa603fda3c12eef92b98daed8d6f0f8f18dd3f757']
    map_hackery["http://BN.depot.battle.net:1119/8481b07338e22a765f0680ea4e49c254c253888017f62c2624b129cac52811fa.s2ma"] = \
        ['us  ', '37627929f99b2fa8c4796740d656ec77a9ae40eedb8aa2d4ca721799930106d4']
    map_hackery["http://BN.depot.battle.net:1119/63002e2b5f749203cf30f62bf32a0dcd0adfd5c3d9090877d87e588107477259.s2ma"] = \
        ['us  ', '4625c1e6dcf26f65b257040596207640e8c1de98fa2de6dfdaab439d631b2a31']

    if replay.map_file.url in map_hackery:
        bytes = 's2ma'
        bytes = bytes + map_hackery[replay.map_file.url][0]
        bytes = bytes + map_hackery[replay.map_file.url][1].decode('hex')
        replay.map_file = DepotFile(bytes)

    return replay


def tooClose(prevMiningLocs, newMiningLoc):
    closePrevMiningLocs = [loc for loc in prevMiningLocs if sqdist(loc, newMiningLoc) <= MINING_BASE_MIN_SQ_DIST]
    return len(closePrevMiningLocs) > 0


@plugin
def MiningBaseIdentifier(replay):
    """ Implements:
            player.miningbases = [list of (base, startframe) for each of this player's bases
                                  that was in a mining location, and the first frame when it
                                  was complete and in a mining location]

            each player's initial base is ignored.

        Requires:
            BaseTracker
    """
    if replay.build < 25446:
        return replay


    try:
      replay.load_map()
    except Exception as e:
      print "Couldn't load map. Won't compute mining bases"
      return replay

    try:
      xmldoc = minidom.parseString(replay.map.archive.read_file('Objects'))
    except Exception as e:
      print "Couldn't read Objects file. Won't compute mining bases"
      return replay

    itemlist = xmldoc.getElementsByTagName('ObjectUnit')
    mineralPosStrs = [ou.attributes['Position'].value for ou in itemlist if 'MineralField' in ou.attributes['UnitType'].value]
    mineralLocs = [tuple([float(num) for num in mps.split(',')[0:2]]) for mps in mineralPosStrs]

    #print set([ou.attributes['UnitType'].value for ou in itemlist])
    #print mineralLocs
    # mineralLocs = [obj.location for obj in replay.objects.values() if (obj.name in mfnames) and hasattr(obj, 'location')]


    landOCCC = ['LandOrbitalCommand', 'LandCommandCenter']
    OCCC_names = ['OrbitalCommand', 'CommandCenter']
    tier1_base_names = ["Hatchery", "Nexus", "CommandCenter"]
    base_names = set(["Hatchery", "Lair", "Hive", "Nexus", "CommandCenter", "CommandCenterFlying", "OrbitalCommand", "OrbitalCommandFlying","PlanetaryFortress"])
    build_base_names = ['BuildHatchery','BuildNexus','BuildCommandCenter']
    BUILDING_SIZE = 3
    TRACKER_GRID_SIZE = 4

    # map from base to its current location or intended landing
    # location, as we walk through the relevant events
    baselocations = dict()

    # map from base to the first time at which it was complete and in
    # a mining location that has not already been used by this player.
    miningbases = dict()

    #
    # each list element is a triple:
    # (frame-when-build-command-happened, (x,y), player)
    #
    ordered_bases = {
        'Hatchery':list(),
        'Nexus':list(),
        'CommandCenter':list(),
    }

    # player.mininglocs is a set of locations where mining bases have been placed
    for player in replay.players:
        player.mininglocs = set()

    # The following code was used to survey many replays and empirically determine the distance
    # from initial bases to the nearest mineral patches.
    #
#    efilter = lambda e: (e.name == 'UnitBornEvent' and e.unit_type_name in tier1_base_names and e.frame == 0)
#    for event in filter(efilter, replay.events):
#       print event.unit.owner
#       isMiningLoc(mineralLocs, event.location)
#    return replay

    efilter = lambda e: (e.name == 'TargetPointCommandEvent' and e.ability_name in landOCCC) or \
              (e.name == 'UnitTypeChangeEvent' and e.unit_type_name in OCCC_names) or \
              (e.name in ['UnitDoneEvent', 'UnitInitEvent'] and e.unit is not None and e.unit.name in base_names) or \
              (e.name == "TargetPointCommandEvent" and e.ability_name in build_base_names)
    for event in filter(efilter, replay.events):
        if hasattr(event, 'unit') and event.unit.owner is None:
          # crazy, but some misparsed replays have events with units without a known owner
          continue
        if event.name == 'TargetPointCommandEvent':
          if event.ability_name in landOCCC:
            selecteds = event.player.selection[event.frame][10].objects
            selected_occcs = [obj for obj in selecteds if obj.type_history.values()[0].name == 'CommandCenter']
            if len(selected_occcs) == 0:
                print "Landing an OC/CC but none selected. WTF. event={}, selecteds={}".format(event, selecteds)
            else:
                selected_occc = selected_occcs[0]
                baselocations[selected_occc] = event.location
                if debug_miningbases and debuglevel_miningbases >= 1:
                    print "{} landing {} at {} at {} (finished at {})".format(event.player, selected_occc, framestr(event.frame), event.location, framestr(selected_occc.finished_at))
          elif event.ability_name in build_base_names:
            x,y,z = event.location
            if debug_miningbases and debuglevel_miningbases >= 1:
              print "{} ordered {} at {} {}".format(event.player, event.ability_name, framestr(event.frame), (x,y))
            base_type = event.ability_name[5:]

            matched_to_unitinit = False

            # sometimes the UnitInit tracker event comes in the same
            # frame as the build command
            for base in event.player.bases:
              if base.started_at == event.frame and (base in baselocations) and abs(baselocations[base][0] - x) < TRACKER_GRID_SIZE and abs(baselocations[base][1] - y) < TRACKER_GRID_SIZE:
                if debug_miningbases and debuglevel_miningbases >= 1:
                  print "Matched to {}".format(base)
                baselocations[base] = (x,y)
                matched_to_unitinit = True
              elif debug_miningbases and debuglevel_miningbases >= 1:
                print "Didnt match. Base: {} {} {}, event {} {} {}".format(base.started_at, base.location[0], base.location[1], event.frame, x, y)

            if not matched_to_unitinit:
              for index, (frame1, (x1,y1), owner) in enumerate(ordered_bases[base_type]):
                if (abs(x-x1) < BUILDING_SIZE and abs(y-y1) < BUILDING_SIZE):
                  if debug_miningbases and debuglevel_miningbases >= 1:
                    print "Same location replaces a previous command"
                  ordered_bases[base_type][index] = (event.frame, (x,y), event.player)
                  break
              else:
                if debug_miningbases and debuglevel_miningbases >= 1:
                  print "No replacement was found"
                ordered_bases[base_type].append( (event.frame, (x,y), event.player) )
        elif event.name == 'UnitInitEvent':
          if debug_miningbases and debuglevel_miningbases >= 1:
            print "{}'s {} did {} at {} at {}".format(event.unit.owner, event.unit, event.name, framestr(event.frame), event.location)
          x,y = event.location
          baselocations[event.unit] = (x,y)
          for index, (frame1, (x1,y1), owner) in enumerate(ordered_bases[event.unit_type_name]):
            if (abs(x-x1) < TRACKER_GRID_SIZE and abs(y-y1) < TRACKER_GRID_SIZE and owner == event.unit_upkeeper):
              baselocations[event.unit] = (x1,y1)
              if debug_miningbases and debuglevel_miningbases >= 1:
                print "Got a match! {} was ordered at {} {} and is tracked at {}".format(event.unit, framestr(frame1), (x1,y1), event.location)
              ordered_bases[event.unit_type_name].pop(index)
              break
        elif event.name in ['UnitTypeChangeEvent', 'UnitDoneEvent']:
            # now the base is landed or done being constructed.
            if debug_miningbases and debuglevel_miningbases >= 1:
                print "{}'s {} did {} at {}".format(event.unit.owner, event.unit, event.name, framestr(event.frame))

            if event.unit in baselocations and event.unit not in miningbases:
                if debug_miningbases and debuglevel_miningbases >= 1:
                    print "and it is at {}".format(baselocations[event.unit])
                if isMiningLoc(mineralLocs, baselocations[event.unit]):
                    if debug_miningbases and debuglevel_miningbases >= 1:
                        print "and it is mining."
                    if tooClose(event.unit.owner.mininglocs, baselocations[event.unit]):
                        if debug_miningbases and debuglevel_miningbases >= 1:
                            print "but too close to a previously-used mining location, forget it"
                    else:
                        miningbases[event.unit] = event.frame
                        event.unit.owner.mininglocs.add(baselocations[event.unit])

    for player in replay.players:
        player.miningbases = [(base,miningbases[base]) for base in miningbases.keys() if base.owner == player]
        player.miningbases = sorted(player.miningbases, key=lambda pair: pair[1])
        if debug_miningbases:
            print "MINING BASES FOR {}".format(player.name.encode('utf-8'))
            for basepair in player.miningbases:
                print "At {}, {} first came to a mining location".format(framestr(basepair[1]), basepair[0])
            for base in player.bases:
              if base not in [basepair[0] for basepair in player.miningbases] and base.started_at > 0 and base.finished_at is not None:
                print "And {} is not a mining base (started at {})".format(base, framestr(base.started_at))

    return replay


@plugin
def BaseTracker(replay):
    base_names_tier_one = set(["Hatchery", "Nexus", "CommandCenter"])
    base_names = set(["Hatchery", "Lair", "Hive", "Nexus", "CommandCenter", "CommandCenterFlying", "OrbitalCommand", "OrbitalCommandFlying","PlanetaryFortress"])

    # Tracker only needed for pre-2.0.8 replays
    if replay.build >= 25446:
        # We still need to provide player.bases though. Tracker events
        # will have already assigned ownership.
        for player in replay.players:
            player.bases = [u for u in replay.objects.values() if u.name in base_names and u.owner == player]
        return replay

    BASE_BUILD_TIME = 100*16
    BUILDING_SIZE = 3
    SCREEN_X, SCREEN_Y = (30,15)

    # we add the following keys to base objects:

    # ordered_at.  The frame of the build command for this base, if we
    # can identify one.  Otherwise it will be unassigned.
    #
    # ordered_at may be used for inferring base lifetime, but be aware
    # that the worker may have a ways to travel before they can
    # actually start construction. Despite that limitation, it is the
    # easiest field to explain, so we are planning to use it.

    # confirmed_at.  The frame of the SelectionEvent or
    # TargetUnitCommandEvent which confirmed the existence of the Base to
    # us.  It very well may have been under construction at that time.
    # Special-case: 0 for each player's initial base.

    # finished_at. When base construction completed. This is the
    # earlier of two things: The first time the base was selected
    # alone and issued a command, or confirmed_at + BASE_BUILD_TIME.
    # Special case: 0 for each player's initial base.
    #
    # Note that the confirmed_at + BASE_BUILD_TIME logic can be wrong
    # for Terran buildings where construction can be delayed.  But
    # this is rare, and using confirmed_at + BASE_BUILD_TIME is very
    # useful, because some players will group their bases when issuing
    # commands.

    # started_at. If we have finished_at, it is finished_at -
    # BASE_BUILD_TIME.  Special case: 0 for the player's initial base.

    # location.  The location of the base, assigned using several
    # different heuristics.

    # owner.  The player that owns the base.  Assigned using several
    # different heuristics.
    #

    # we add the following to player objects.
    #
    # bases.  a list of bases owned by that player.

    # A "known base" is either one of the starting bases, or we have
    # alrady seen an event that refers to the base object (not just a
    # build command).  For non-starting bases, it has been matched to
    # a build command.  And it has been assigned values (non-final
    # values) for all the fields above.
    known_bases = set()

    #
    # we are matching base-build commands to actual bases.
    #
    # the following lists are logically a list of _unmatched_
    # base-build commands from all players.  they are in chronological
    # order, except that if a building command physically overlaps
    # with a previous one, then the new command replaces the old
    # command in that slot in the list.
    #

    #
    # each list element is a triple:
    # (frame-when-build-command-happened, (x,y), player)
    #
    ordered_bases = {
        'Hatchery':list(),
        'Nexus':list(),
        'CommandCenter':list(),
    }

    # Minimal Setup
    for player in replay.players:
        player.bases = list()

    def base_exists(base, x, y, possible_owner, event_frame, event):
        # Try to match this base to its build command
        # Try to register the base's ownership

        # some strange event in http://ggtracker.com/matches/2720737/replay with a base with id 0.
        if base.id == 0:
            return

        #print "base_exists({}, {}, {}, {}, {}, {})".format(base, x, y, possible_owner, event_frame, event)

        owner = None
        base_name = base.type_history.values()[0].name
        if base_name in base_names_tier_one:
            # First, are there build commands that were near the current screen location?
            possible_matches = list()
            for index, (frame1, (x1,y1), owner) in enumerate(ordered_bases[base_name]):
                #print "Trying to match event {}, {} to build command at {}, {}".format(x, y, x1, y1)
                if (abs(x-x1) < SCREEN_X and abs(y-y1) < SCREEN_Y):
                    possible_matches.append(index)

            # If not, then we'll just look at all the build commands from that player
            if len(possible_matches) == 0 and player:
                #print "No on screen locations found (backspace?), falling back to ownership rules"
                for index, (frame1, (x1,y1), owner) in enumerate(ordered_bases[base_name]):
                    if owner == possible_owner:
                        possible_matches.append(index)

            if len(possible_matches) == 0:
                print "No matching build commands found for newly-discovered base {}, oh nooooes! Event={}".format(base, event)
                return
            #elif len(possible_matches) > 1:
                #print "Multiple matching build commands found for selected base {}, going to arbitrarily associate it with the oldest base-build command. Event={}".format(base, event)

            match = possible_matches[0]

            frame, (x,y), owner = ordered_bases[base_name][match]
            #print "Associating base {} with build command at {}. Event={}".format(base, str(Length(seconds=frame/16)), event)

            base.ordered_at = frame
            base.started_at = None
            base.confirmed_at = event_frame
            base.finished_at = None
            base.location = (x,y)
            del ordered_bases[base_name][match]

        if not base.owner:
            if owner:
                base.owner = owner
            else:
                base.owner = possible_owner

        if base.owner:
            base.owner.units.add(base)
            base.owner.bases.append(base)
            known_bases.add(base)


    for event in replay.events:

        # Track camera locations
        if event.name == "CameraEvent":
            event.player.camera = (event.x, event.y)

        # Capture Base Build Commands
        if event.name == "TargetPointCommandEvent" and event.ability_name in ['BuildHatchery','BuildNexus','BuildCommandCenter']:
            #print divmod(event.frame/16, 60), event.player, event.ability_name, event.location
            x,y,z = event.location
            base_type = event.ability_name[5:]
            for index, (frame1, (x1,y1), owner) in enumerate(ordered_bases[base_type]):
                if (abs(x-x1) < BUILDING_SIZE and abs(y-y1) < BUILDING_SIZE):
                    # Same location replaces a previous command
                    ordered_bases[base_type][index] = (event.frame, (x,y), event.player)
                    break
            else:
                # No replacement was found
                ordered_bases[base_type].append( (event.frame, (x,y), event.player) )

        # Use SelectionEvents to confirm that the base was actually started
        if event.name == "SelectionEvent":
            selected_bases = [u for u in event.objects if u.name in base_names]

            # When a base is selected in the first 30 seconds of the
            # game, we use special initialization logic
            if selected_bases and event.frame < 120*16:
                base = selected_bases[0] #only 1 base is possible at this point
                if base not in known_bases:
                    #print divmod(event.frame/16, 60), event.player, "Found new starting base", base
                    base.ordered_at = 0
                    base.started_at = 0
                    base.confirmed_at = 0
                    base.finished_at = 0
                    if hasattr(event.player, 'camera'):
                        base.location = event.player.camera

                    if not base.owner:
                        # the following line is not guaranteed
                        # correct, but if youre not the first player
                        # to select your own base, you are playing the
                        # wrong game
                        base.owner = event.player
                        base.owner.units.add(base)
                    base.owner.bases.append(base)

                    # print "STARTING BASE: ", base
                    known_bases.add(base)
                continue;

            # Were any bases selected that we've never seen before?
            unknown_bases = set(selected_bases) - known_bases
            if not unknown_bases:
                continue

            # So this is a SelectionEvent involving one or more bases
            # that we've never seen before.
            x,y = event.player.camera
            for base in unknown_bases:
                base_exists(base, x, y, event.player, event.frame, event)

        # Sometimes a base will be targeted (by an enemy, or perhaps
        # your queen) before it is Selected.  We can use the Target event as our clue that the building exists.
        if event.name == "TargetUnitCommandEvent" and (event.target.name in base_names):
            base = event.target
            if base not in known_bases:
                x,y = event.player.camera
                base_exists(base, x, y, None, event.frame, event)




        # If a single base is selected and certain abilities are used, then we know the base was successfully completed
        ability_names = set(["SetWorkerRally","SetUnitRally","TrainSCV","TrainDrone","TrainProbe","TrainMothershipCore","ChronoBoost","LiftCommandCenter","UpgradeToOrbitalCommand","UpgradeToLair"])

        if hasattr(event, 'ability') and event.ability_name in ability_names:
            selected_objs = event.player.selection[event.frame][10].objects
            selected_bases = [u for u in selected_objs if u.name in base_names]
            if len(selected_bases) == 1 and (not hasattr(selected_bases[0], "finished_at") or selected_bases[0].finished_at is None):
                selected_bases[0].finished_at = event.frame

    for base in known_bases:
        if hasattr(base, 'confirmed_at') and base.last_activity > (base.confirmed_at + BASE_BUILD_TIME) and base.name in base_names_tier_one:
            if base.finished_at is None:
                base.finished_at = base.confirmed_at + BASE_BUILD_TIME
            else:
                base.finished_at = min(base.finished_at, base.confirmed_at + BASE_BUILD_TIME)

        if hasattr(base, 'finished_at') and base.finished_at and base.name in base_names_tier_one:
            base.started_at = max(0, base.finished_at - BASE_BUILD_TIME)

        if hasattr(base, 'started_at') and base.started_at is not None:
            base.first_activity = min(base.started_at, base.first_activity)

    # compute bases_by_minute array, even though it aint used as of 20130404
#    replayMinutesCompleted = replay.frames/960
#    for player in replay.players:
#        player.bases_by_minute = [0] * (replayMinutesCompleted + 1)
#        for base in player.bases:
#            if base.ordered_at and base.last_activity:
#                firstMinute = int(math.ceil((base.ordered_at + BASE_BUILD_TIME)/960.0))
#                lastMinute = int(math.ceil(base.last_activity/960.0))
#                for i in range(firstMinute, lastMinute+1):
#                    player.bases_by_minute[i] = player.bases_by_minute[i] + 1

    # show DJ some diagnostics
    if False:
        for player in replay.players:
            print "PLAYER {}".format(player)
            for base in player.bases:
                baseloc = None
                if hasattr(base, 'location'):
                    baseloc = base.location
                print "base {} at {}: ".format(base, baseloc),
                for timestamp_name in ['first_activity', 'last_activity', 'ordered_at', 'confirmed_at', 'finished_at', 'started_at']:
                    if hasattr(base, timestamp_name) and getattr(base, timestamp_name) is not None:
                        display_value = str(Length(seconds=int(getattr(base, timestamp_name)/16)))
                    else:
                        display_value = 'None'
                    print timestamp_name + ': ' + display_value + ', ',
                print ''


    return replay


@plugin
def ZergMacroTracker(replay):
    INJECT_TIME = 40 * 16

    debug_injects = False

    for player in replay.players:
        player.hatches = dict()

    efilter = lambda e: e.name.endswith("TargetUnitCommandEvent") and hasattr(e, "ability") and e.ability_name == "SpawnLarva"
    for event in filter(efilter, replay.events):
        owner = event.player
        target_hatch = event.target
        target_hatch_id = event.target.id
        if target_hatch_id not in owner.hatches:
            target_hatch.injects = [event.frame]
            owner.hatches[target_hatch_id] = target_hatch
        else:
            # If not enough time has passed, the last one didn't happen
            if event.frame - target_hatch.injects[-1] < INJECT_TIME:
                # print "Previous inject on {0} at {1} failed".format(target_hatch, target_hatch.injects[-1])
                target_hatch.injects[-1] = event.frame
            else:
                target_hatch.injects.append(event.frame)

    # Consolidate Lairs and Hives back into the originating Hatcheries
    for player in replay.players:
        if player.play_race != 'Zerg': continue

        hatches = dict()
        macro_hatches = dict()
        for final_hatch in player.hatches.values():
            hatches[(final_hatch.id,final_hatch.type)] = final_hatch

            if len(final_hatch.injects) == 0:
                continue

            # Throw out injects that don't finish
            final_hatch.injects.sort()

            if final_hatch.injects[-1]+INJECT_TIME > final_hatch.died_at:
                final_hatch.injects.pop()

            if len(final_hatch.injects) > 1:
                # Should we use the "most upgraded" type here?
                macro_hatches[(final_hatch.id,final_hatch.type)] = final_hatch

                # Calculate Utilization
                final_hatch.inject_time = len(final_hatch.injects) * INJECT_TIME
                final_hatch.active_time = final_hatch.died_at - final_hatch.injects[0]
                final_hatch.utilization = final_hatch.inject_time/float(final_hatch.active_time)

        player.hatches = hatches
        player.macro_hatches = macro_hatches

        if len(player.macro_hatches) > 0:
            total_inject_time = sum([hatch.inject_time for hatch in player.macro_hatches.values()])
            total_active_time = sum([hatch.active_time for hatch in player.macro_hatches.values()])
            player.race_macro = total_inject_time/float(total_active_time)
        else:
            player.race_macro = 0

        if debug_injects:
            print 'Player {} active total: {}, inject total: {}, race macro: {:.15f}'.format(player, str(Length(seconds=int(total_active_time)/16)), str(Length(seconds=int(total_inject_time)/16)), player.race_macro)
            print 'Bases'
            print '---------------------------------------'
            for hatch in player.hatches.values():
                if hasattr(hatch, 'injects'):
                    if hasattr(hatch, 'active_time'):
                        print 'Active:{} Injects:{} Died:{} '.format(str(Length(seconds=int(hatch.active_time)/16)), str(Length(seconds=int(hatch.inject_time)/16)), str(Length(seconds=int(hatch.died_at)/16)))
                    print "{} Injects: ".format(hatch),
                    for inject in hatch.injects:
                        print str(Length(seconds=int(inject)/16)) + ' ',
                    print ''
            print '---------------------------------------'
            print ''
            print ''


    return replay

@plugin
def ProtossTerranMacroTracker(replay):
    """ Implements: protoss/terran max-energy tracking
        Requires: SelectionTracker
                  BaseTracker
    """

    # we simulate nexus/orbital energy for each player's bases,
    # assuming that energy starts accumulating at finished_at.

    # We could have used ordered_at + BASE_BUILD_TIME, but that would
    # be inaccurate and harsh for bases that were built by a worker
    # that had a ways to travel.  finished_at is sometimes later than
    # the true completion time, but let's be generous.  if Nexus/Orbital
    # energy simulates below zero, then we clamp it to zero and the
    # simulation is more accurate going forward from that point.

    # we add the following fields to Nexus/Orbital objects:
    #  as_of_frame        the frame at which the following fields are valid
    #  start_energy_frame the frame at which energy accumulation started
    #  energy             the energy of the Nexus/Orbital at time as_of_frame
    #  maxouts            list of times at which we were at max energy, each being [start_frame, end_frame]
    #  chronoboosts       list of chronoboost frames
    #  mules              list
    #  scans              list
    #  supplydrops        list

    # Algorithm:
    # for each chronoboost/mule/etc, in order
    #  pick which base did it
    #  update that base's stats to the time just before the event
    #  update the base for the event
    # game over, final adjustment to all base stats
    # compute each player's macro score

    CHRONO_COST = 25
    ORBITAL_ABILITY_COST = 50
    ENERGY_REGEN_PER_FRAME = 0.5625 / 16.0
    NEXUS_MAX_ENERGY = 100
    ORBITAL_MAX_ENERGY = 200
    ORBITAL_START_ENERGY = 50

    # pick the closest base with enough energy, as per
    # http://www.teamliquid.net/forum/viewmessage.php?topic_id=406590
    #
    # or if no bases have enough energy, or they dont have locations,
    # return the base with the most energy.
    #
    def which_base(event):
        owner = event.player
        min_base_distance = 999999
        min_base = None
        selected_objects = owner.selection[event.frame][0x0a].objects
        selected_bases = [obj for obj in selected_objects if obj.name in ['Nexus', 'OrbitalCommand', 'OrbitalCommandFlying']]

        # sometimes due to event-ordering madness, we think there are
        # no bases selected at the time of an event.  in those
        # cases, we'll attempt to recover by just looking at all the
        # player's bases.
        if len(selected_bases) == 0:
            selected_bases = event.player.bases

        if len(selected_bases) == 0:
            print "No Bases selected and player has no bases registered yet. I give up"
            return None

        if event.player.play_race == 'Protoss':
            ability_cost = CHRONO_COST
        else:
            ability_cost = ORBITAL_ABILITY_COST

        #print "event {}".format(event)
        #print "which {} {}".format(event.location[0], event.location[1])
        for base in selected_bases:
            update_to_frame(base, event.frame, "which", None)
            if hasattr(base, 'energy') and hasattr(base, 'location') and base.energy > ability_cost:
                if not hasattr(event, 'location'):
                    print "How can this event have no location?!"
                    print "event {}".format(event.__str__().encode('utf-8'))
                    return None
                #print "considering base {} by location/energy".format(base)
                diff_x = base.location[0] - event.location[0]
                diff_y = base.location[1] - event.location[1]
                sqdiff = diff_x * diff_x + diff_y * diff_y
                if sqdiff < min_base_distance:
                    min_base_distance = sqdiff
                    min_base = base
                #print "picking base at location {} {}".format(base.location[0], base.location[1])

        if min_base is not None:
            return min_base

        max_energy = -1
        max_energy_base = None
        for base in selected_bases:
            #print "considering base {} with energy {}".format(base, base.energy if hasattr(base, 'energy') else 'None')
            if hasattr(base, 'energy'):
                if base.energy > max_energy:
                    max_energy = base.energy
                    max_energy_base = base
            #print "picking base with energy {}".format(max_energy)

        return max_energy_base


    # roll the base state forward to the given frame. no energy abilities
    # occur in the intervening time.
    def update_to_frame(base, frame, reason, event):
        #print "Updating base {} to frame {}".format(base, frame)
        if not hasattr(base, "start_energy_frame"):
            if getattr(base, 'finished_at', None) != None:
                base.maxouts = []
                if base.name == 'Nexus':
                    base.energy = 0
                    base.chronoboosts = []
                    if base.finished_at == 0:
                        base.start_energy_frame = 0
                    else:
                        base.start_energy_frame = base.finished_at
                elif base.name == 'OrbitalCommand' or base.name == 'OrbitalCommandFlying':
                    base.energy = ORBITAL_START_ENERGY
                    base.mules = []
                    base.scans = []
                    base.supplydrops = []

                    #print "Looking for Orbitals first time as an Orbital, history={}".format(base.type_history.items())

                    # find the first time we changed type to orbital. It is important
                    # to note that we can change to orbital several times as we lift/land
                    for frame, utype in base.type_history.items():
                        if utype.name == 'OrbitalCommand':
                            base.start_energy_frame = frame
                            break;

                else:
                    # only Nexus and OrbitalCommand have energy
                    return

                if not hasattr(base, 'start_energy_frame'):
                  print "cant figure out the start-energy frame, not gonna touch it"
                  return
                base.as_of_frame = base.start_energy_frame
            else:
                #print "this base has no finished_at. not gonna touch it. base={}".format(base)
                return
        if frame < base.as_of_frame:
            # a base that is still as-of its start energy frame may
            # receive update_to_frame calls from an earlier
            # time. thats OK.
            #
            # any other out-of-order scenario is a bug.
            #
            if base.as_of_frame != base.start_energy_frame:
                print "update_to_frame called out of time order. {} before {}. reason={}, event={}".format(frame, base.as_of_frame, reason, event)
            return
        if frame == base.as_of_frame:
            #print "no time has passed, nothing to do. now={}".format(frame)
            return

        if base.name == 'Nexus':
            max_energy = NEXUS_MAX_ENERGY
        else:
            max_energy = ORBITAL_MAX_ENERGY
        # energy was already at max. extend the last maxout and we're
        # done here.
        if base.energy == max_energy:
            base.maxouts[-1][1] = frame
            base.as_of_frame = frame
            return

        new_energy = base.energy + ENERGY_REGEN_PER_FRAME * (frame - base.as_of_frame)

        if new_energy < max_energy:
            base.energy = new_energy
        else:
            energy_to_max = float(max_energy - base.energy)
            time_to_max = energy_to_max / ENERGY_REGEN_PER_FRAME
            maxout_start_time = base.as_of_frame + time_to_max
            base.maxouts.append([maxout_start_time, frame])
            base.energy = max_energy

        base.as_of_frame = frame

    def use_ability(base, event):
        update_to_frame(base, event.frame, "use_ability", None)
        cost = ORBITAL_ABILITY_COST
        if event.ability_name == 'ChronoBoost':
            cost = CHRONO_COST
            base.chronoboosts.append(event.frame)
        elif event.ability_name == 'CalldownMULE':
            base.mules.append(event.frame)
        elif event.ability_name == 'ExtraSupplies':
            base.supplydrops.append(event.frame)
        else:
            base.scans.append(event.frame)


        base.energy = base.energy - cost
        if base.energy < 0:
            #print "base energy at {} at frame {}. base={}".format(base.energy, frame, base)
            base.energy = 0

    efilter = lambda e: hasattr(e, "ability") and e.ability_name in ['ChronoBoost', 'CalldownMULE', 'ExtraSupplies', 'ScannerSweep']
    # TODO also catch OrbitalLand events and update our estimate of the base's location
    for event in filter(efilter, replay.events):
        base = which_base(event)
        if base is None:
            print "Cant figure out which Base this Chronoboost/Scan/etc was for. Ignoring it :("
        else:
            update_to_frame(base, event.frame, "ability", event)
            use_ability(base, event)

    for player in replay.players:
        if player.play_race == 'Zerg': continue

        total_maxout_time = 0
        total_active_time = 0

        for base in player.bases:
            if base.name in ['Nexus', 'OrbitalCommand', 'OrbitalCommandFlying']:
                update_to_frame(base, base.died_at, "final", None)
                if hasattr(base, 'maxouts') and hasattr(base, 'start_energy_frame'):
                    total_maxout_time = total_maxout_time + sum([(maxout[1] - maxout[0]) for maxout in base.maxouts])
                    base.active_time = (base.died_at - base.start_energy_frame)
                    total_active_time = total_active_time + base.active_time


        if total_active_time > 0:
            player.race_macro = 1.0 - total_maxout_time/float(total_active_time)
        else:
            player.race_macro = 0

        if False:
            print 'Player {} active total: {}, maxout total: {}, race macro: {:.15f}'.format(player, str(Length(seconds=int(total_active_time)/16)), str(Length(seconds=int(total_maxout_time)/16)), player.race_macro)
            print 'Bases'
            print '---------------------------------------'
            for base in player.bases:
                if hasattr(base, 'maxouts'):
                    print "Player {} Base {} active time {}".format(player, base, Length(seconds=int(getattr(base,'active_time', 0)/16)))
                    if base.name == 'Nexus':
                        print "Chronoboosts: ",
                        for boost in base.chronoboosts:
                            print str(Length(seconds=int(boost)/16)) + ' ',
                        print ''
                    else:
                        for name, thelist in [('Scans: ', base.scans), ('MULEs: ', base.mules), ('Supply: ', base.supplydrops)]:
                            print name
                            for frame in thelist:
                                print str(Length(seconds=int(frame)/16)) + ' ',
                            print ''

                    print "Maxouts: ",
                    for maxout in base.maxouts:
                        print str(Length(seconds=int(maxout[0])/16)) + '-' + str(Length(seconds=int(maxout[1])/16)) + ' ',
                    print ''
            print '---------------------------------------'
            print ''
            print ''

    return replay


# this plugin sets replay.eblob to be a list of engagements. Each engagement is a list, containing:
# * frame when engagement started
# * frame when engagement ended
# * value of team 1's army at start of engagement
# * value of team 1's army units lost during engagement
# * value of team 1's non-army units and buildings lost during engagement
# * value of team 2's army at start of engagement
# * value of team 2's army units lost during engagement
# * value of team 2's non-army units and buildings lost during engagement
@plugin
def EngagementTracker(replay):

    # cant consistently do engagements for pre 2.0.7.  sad but its too
    # hard to explain the differences
    if replay.build < 25446:
        replay.eblob = []
        return replay

    debug_engagement = False
    debuglevel = 0

    eblob = []

    owned_units = []
    for obj in replay.objects.values():
        if obj.owner is not None:
            if (replay.build >= 25446 or obj.is_army) and obj.minerals is not None:
                owned_units.append(obj)

    MAX_DEATH_SPACING_FRAMES = 160.0
    INTERESTING_ENGAGEMENT = 0.1

    owned_units = sorted(owned_units, key=lambda obj: obj.died_at)

    engagements = []
    dead_units = []
    current_engagement = None
    for unit in owned_units:
        # print Length(seconds=int(dead.died_at/16)), dead

        if (unit.killed_by is not None or replay.build < 25446) and (unit.minerals + unit.vespene > 0):
            dead = unit
            dead_units.append(dead)
            if current_engagement is None or (dead.died_at - current_engagement[2] > MAX_DEATH_SPACING_FRAMES):
                current_engagement = [[dead], dead.died_at, dead.died_at]
                engagements.append(current_engagement)
            else:
                current_engagement[0].append(dead)
                current_engagement[2] = dead.died_at

    if debug_engagement:
        print 'Estrt Eend ',
        for team in replay.teams:
            print 'ArmyS', 'Killd', 'KilEc', '%Died', 'Reinf',
        print ''

    engagment_num = 0
    for engagement in engagements:
        killed = defaultdict(int)   # killed[123] means army units owned by 123 that were killed
        stuff_at_start = defaultdict(int)
        born_during_fight = defaultdict(int)
        killed_econ = defaultdict(int)   # killed_econ[123] means non-army units/buildings owned by 123 that were killed
        for dead in engagement[0]:
            deadvalue = dead.minerals + dead.vespene
            if dead.is_army:
                killed[dead.owner.team] += deadvalue
                if debug_engagement and debuglevel >= 1 and deadvalue > 0:
                    print "army killed @ {}: {} {}".format(dead.died_at, dead.name, deadvalue)
            elif replay.build >= 25446:
                killed_econ[dead.owner.team] += deadvalue
                if debug_engagement and debuglevel >= 1 and deadvalue > 0:
                    print "eco killed @ {}: {} {}".format(dead.died_at, dead.name, deadvalue)

        for unit in owned_units:
            if unit.finished_at < engagement[1] and unit.died_at >= engagement[1]:
                stuff_at_start[unit.owner.team] += unit.minerals + unit.vespene
            if unit.finished_at >= engagement[1] and unit.finished_at < engagement[2]:
                born_during_fight[unit.owner.team] += unit.minerals + unit.vespene

        interesting = False
        if engagement[2] > engagement[1]:
            for team in replay.teams:
                if (stuff_at_start[team] > 0) and ((float(killed[team] + killed_econ[team]) / stuff_at_start[team]) > INTERESTING_ENGAGEMENT):
                    interesting = True

        if debug_engagement and debuglevel >= 1 and not interesting:
            print "Engagement {} {}".format(engagement[1], engagement[2])
            for team in replay.teams:
                print "Team {}, started with {}, total killed {}".format(team.number, stuff_at_start[team], killed[team] + killed_econ[team])

#        interesting = True

        if interesting:
            new_engagement_stat = [engagement[1], engagement[2]]

            team_stats = dict()
            for teamnum in range(1, len(replay.teams) + 1):
                team_stat = [0, 0, 0]
                team_stats[teamnum] = team_stat

            if debug_engagement:
                print Length(seconds=int(engagement[1]/16)), Length(seconds=int(engagement[2]/16)),
            for team in replay.teams:
                killedpct = 0
                if stuff_at_start[team] > 0:
                    killedpct = (100.0 * (killed[team] + killed_econ[team]))/stuff_at_start[team]
                if debug_engagement:
                    print '{:5} {:5} {:5} {:5.1f} {:5}'.format(stuff_at_start[team], killed[team], killed_econ[team], killedpct, born_during_fight[team]),

                team_stats[team.number][0] = stuff_at_start[team]
                team_stats[team.number][1] = killed[team]
                team_stats[team.number][2] = killed_econ[team]
            if debug_engagement:
                print ''

            for teamnum in range(1, len(replay.teams) + 1):
                new_engagement_stat.extend(team_stats[teamnum])

            eblob.append(new_engagement_stat)


    replay.eblob = eblob

    if debug_engagement:
        pprint(eblob)

    if False:
        for unit in owned_units:
            if unit.owner == None:
                ownername = 'None'
            else:
                ownername = unit.owner.name
            print Length(seconds=int(unit.died_at/16)),
            print unit.name,
            print ownername,
            print unit in dead_units

    return replay


# returns the location of that player's starting base
def StartingBaseLocation(player):
  result = None
  for base in player.bases:
    if base.started_at == 0:
      result = base.location
      break
#  if result == None:
#    basestarts = [b.started_at for b in player.bases]
#    print "How can there be no starting base location for {} (bases={}, {})?".format(player, player.bases, basestarts)
  return result


REALLY_BIG_NUMBER = 1000000

def MinimumBaseDistance(replay):
  minimumDistance = REALLY_BIG_NUMBER
  baselocs = [StartingBaseLocation(player) for player in replay.players]
  for basepair in itertools.combinations(baselocs, 2):
    if basepair[0] == None or basepair[1] == None:
#      print "Weird, a player has no starting base in {} ({}).".format(replay.filename, replay.release_string)
      continue
    diff_x = basepair[0][0] - basepair[1][0]
    diff_y = basepair[0][1] - basepair[1][1]
    dist = math.sqrt(diff_x * diff_x + diff_y * diff_y)
    if dist < minimumDistance:
      minimumDistance = dist

  return minimumDistance


# this plugin sets player.first_scout_command_frame to the frame in
# which the first scout command was issued.
#
# a command is counted as a scouting command if a mobile unit is given
# any kind of target-location command (move, attack-move, even build a
# building) that is far enough away from that player's main base.
#
# The required distance is HALF the distance between the two closest
# main bases.
#
# Several kinds of scouting are currently not recognized, in
# particular scans.
#
@plugin
def ScoutingTracker(replay):

  #TODO recognize Scans as a form of scouting
  #TODO confirm that changeling scouts are counted

  mbd = MinimumBaseDistance(replay)
  half_mbd_squared = (mbd / 2.0) ** 2

  efilter = lambda e: (isinstance(e, TargetPointCommandEvent) or isinstance(e, TargetUnitCommandEvent))
  for player in replay.players:

    player.first_scout_command_frame = None
    if mbd == REALLY_BIG_NUMBER:
      # if we dont have good base location data, then we can't make
      # good scouting estimates
      continue

    startingloc = StartingBaseLocation(player)
    aes = filter(efilter, player.events)
    for ae in aes:
      commanded_units = player.selection[ae.frame][0x0a].objects
      movable_units = [w for w in commanded_units if (w.is_worker or w.is_army)]
      if len(movable_units) > 0:
        diff_x = startingloc[0] - ae.location[0]
        diff_y = startingloc[1] - ae.location[1]
        sqdiff = diff_x * diff_x + diff_y * diff_y
        if sqdiff > half_mbd_squared:
#          print framestr(ae.frame), player, player.selection[ae.frame][0x0a].objects
          player.first_scout_command_frame = ae.frame
          break

  return replay

# this plugin sets each player's player.upgrades to a list like:
# [[upgrade_name_1, frame_when_completed],
#  [upgrade_name_2, frame_when_completed], ...
# ]
@plugin
def UpgradesTracker(replay):
  for player in replay.players:
    player.upgrades = []

  # filter out the 'upgrades' at time 0 because those are dances and
  # rewards which are vile spam that just fills up our matchblob
  efilter = lambda e: (isinstance(e, UpgradeCompleteEvent) and e.frame > 0)
  ues = filter(efilter, replay.tracker_events)
  for ue in ues:
    if hasattr(ue, 'player') and ue.player is not None:
      ue.player.upgrades.append([ue.upgrade_type_name, ue.frame])

  return replay

