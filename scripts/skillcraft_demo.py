#!/usr/bin/env python

import sys
import os

if 'GGFACTORY_CACHE_DIR' not in os.environ:
  os.environ['GGFACTORY_CACHE_DIR'] = '/tmp'

from sc2reader.events import *
from sc2parse import ggfactory
import sc2reader
from sc2parse.skillcraft import ScreenFixationIDT, PACStats

factory = sc2reader.factories.DoubleCachedSC2Factory(os.environ['GGFACTORY_CACHE_DIR'], 0)
factory.register_plugin('Replay', ScreenFixationIDT())
factory.register_plugin('Replay', PACStats())

replay = factory.load_replay(sys.argv[1])

print
print
print

for player in replay.players:
  fixation_starts = [fix[0] for fix in player.fixations]
  fixation_ends = [fix[1] for fix in player.fixations]
  action_latencies = []
  firstevent = None
  fixation_start_frame = 0

  action_latency_timestamps = player.action_latency * 4.0
  action_latency_real_seconds = player.action_latency / (16.0 * 1.38)
  print "Player {} had action latency = {:.1f} frames, {:.1f} timestamps, {:.2f} real seconds".format(player, player.action_latency, action_latency_timestamps, action_latency_real_seconds)
  
  verbose = False

  print "There were {} camera fixations for {}".format(len(player.fixations), player)
  print "Here are all camera-moving events, annotated to show fixations:"
  for e in player.events:
    if isinstance(e, CameraEvent):
      if e.frame in fixation_starts:
        if verbose:
          print " START FIXATION {} @ {} = {}.{}".format(fixation_starts.index(e.frame), e.frame, Length(seconds=int(e.frame/16)), e.frame%16)
        minx = e.x
        maxx = e.x
        miny = e.y
        maxy = e.y
        firstevent = None
        fixation_start_frame = e.frame
      minx = min([e.x, minx])
      miny = min([e.y, miny])
      maxx = max([e.x, maxx])
      maxy = max([e.y, maxy])
      if verbose:
        print "{:<5}\t{: <70}\tdisp={:.1f} / not an action".format(e.frame, e, (maxx - minx) + (maxy - miny))
    else:
      if fixation_start_frame > 0 and firstevent is None:
        if (isinstance(e, GetControlGroupEvent)):
          if verbose:
            print "{:<5}\t{: <70}\tIGNORED, latency would have been={}".format(e.frame, e, e.frame - fixation_start_frame)
        elif isinstance(e, SelectionEvent) and len(e.new_unit_info) == 0:
          if verbose:
            print "{:<5}\t{: <70}\tSELD IGNORED, latency would have been={}".format(e.frame, e, e.frame - fixation_start_frame)
        else:
          firstevent = e
          action_latency = e.frame - fixation_start_frame
          action_latencies.append(action_latency)
          if verbose:
            print "{:<5}\t{: <70}\tFIRST ACTION, latency={}".format(e.frame, e, action_latency)

  num_PACs = len(action_latencies)
  action_latency_frames = float(sum(action_latencies)) / num_PACs
  action_latency_timestamps = action_latency_frames * 4.0
  action_latency_real_seconds = action_latency_frames / (16.0 * 1.38)
  print "There were {} fixations with actions, action latency = {} frames, {} timestamps, {} real seconds".format(num_PACs, action_latency_frames, action_latency_timestamps, action_latency_real_seconds)
          


