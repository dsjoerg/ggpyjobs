import argparse
from sc2reader.factories.plugins.utils import plugin
from sc2reader.events import *
from datetime import datetime

SHOW_SPEED = False

@plugin
def ScreenFixationIDT(replay):
  """Adapted by David Joerg from algorithm written at Cognitive Science
Lab, Simon Fraser University (http://cslab-sfu.ca/) for their
Skillcraft project (http://skillcraft.ca/)

Fixation algorithm (Dispersion threshold identification):

This is a fixation algorithm originally used in eye tracking
research. Instead of gaze data from an eye tracker we use X and Y
coordinates from SC2 games. We also use the replay timestamp
information in the algorithm.

(DJ Note: that the term "timestamp" appears to come from SC2Gears, and
that there are 64 timestamps per game second)

In eye tracking any gaze below around 200ms is not considered a
fixation. So we set a minimum duration threshold. Here we use 20 as
the minimum duration threshold, this is because the units in the
script are in timestamps. There are 88.53 timestamps in a second so 20
timestamps is around 200ms.

(DJ Note: the above numbers are correct, remember that there are ~1.38
game seconds per real second and they are talking about real seconds
in the paragraph above).

Dispersion threshold is set as well.

In the algorithm a 'moving window' runs along consecutive data points
assigning sets of points either into fixations or discarding them if
they're not in a fixation. The duration threshold determines the
minimum window size.

Starting from our first data points, when we have our first window,
determined by the duration threshold, we then sum up the differences
between data points in that window
((max[X]-min[X])+(max[Y])-min[y])). If the dispersion of these points
is less than or equal to the dispersion threshold then we know we have
a fixation.

Now that we have a fixation we expand the window by one data point to
the right. We do this until the difference between max and mix in the
window is higher than the dispersion threshold. Once we reach that
point the entire window is recognized as one whole fixation with the
centre of the fixation being the centre data point of that window. Now
we create a new window towards the right basing its size on the
duration threshold.

On the other hand if the dispersion in the first window was greater
than the dispersion threshold then we don't have a fixation and we
discard one datapoint from the left. Now we create a new window
towards the right, its size based on the duration threshold.

In this way we keep moving along the data points determining all the sets of fixations. 

Pseudocode for IDT algorithm(Salvucci & Goldberg (2000)):

'While there are still points
  initialize window over first points to cover duration threshold

  If dispersion of window points <= threshold
    add additional points to the window until dispersion>threshold
    
    note a fixation at the centroid of the window points
    remove window points from the points
  Else
    remove first point from the points

PAC algorithms:

Any fixation with one or more action in it is considered a PAC.

Action latency is the time between the start of the PAC and the first
action in that PAC.


For each player object, a fixations attribute is added to it, which is an array of [start-frame, end-frame].
  """

  if SHOW_SPEED:
    start_time = datetime.now()

  for player in replay.players:
    ScreenFixationIDTForPlayer(player)

  if SHOW_SPEED:
    end_time = datetime.now()
    print "IDT: {} seconds".format((end_time - start_time).total_seconds())

  return replay


def ScreenFixationIDTForPlayer(player):
  DispersionThreshold = 6
  DurationThreshold = 5     # each 'timestamp' is 1/4 of a frame (aka gameloop);  20 timestamps = 5 frames

  player.fixations = []

  efilter = lambda e: isinstance(e, CameraEvent)
  camera_events = filter(efilter, player.events)
  fs = 0
  fe = 0
  nRows = len(camera_events)

  # while there are still points
  while fe < nRows:

    # loop to find a point such that we pass the the duration threshold
    for i in range(fs, nRows + 1):
      if i == nRows:
        return

      if camera_events[i].frame - camera_events[fs].frame > DurationThreshold:
        fe = i - 1
        break


    # we care about fs through fe, inclusive
    max_x = camera_events[fs].x
    min_x = camera_events[fs].x
    max_y = camera_events[fs].y
    min_y = camera_events[fs].y
    for event in camera_events[fs+1:fe+1]:
      max_x = max(event.x, max_x)
      min_x = min(event.x, min_x)
      max_y = max(event.y, max_y)
      min_y = min(event.y, min_y)

    # if dispersion of window points <= threshold
    if (max_x-min_x) + (max_y-min_y) <= DispersionThreshold:
        
      # add additional points to the window until dispersion > threshold
      while fe < nRows-1 and (max_x-min_x) + (max_y-min_y) <= DispersionThreshold:
            
        fe = fe + 1
        max_x = max(max_x, camera_events[fe].x)
        min_x = min(min_x, camera_events[fe].x)
        max_y = max(max_y, camera_events[fe].y)
        min_y = min(min_y, camera_events[fe].y)

      if camera_events[fe].frame - camera_events[fs].frame >= DurationThreshold:
        # note a fixation
        player.fixations.append([camera_events[fs].frame, camera_events[fe].frame])

      # remove window points from points
      fs = fe

    else:
      # remove first point from points
      fs = fs + 1


@plugin
def PACStats(replay):
  """
  Computes action_latency for each player, which is the average # of frames until the first action in a PAC
  
  The result is player.action_latency, which is measured in frames

  Requires that the ScreenFixationIDT plugin has been run first
  """

  if SHOW_SPEED:
    start_time = datetime.now()

  for player in replay.players:
    action_latencies = []
    action_filter = lambda e: not (isinstance(e, CameraEvent) or isinstance(e, GetControlGroupEvent) or (isinstance(e, SelectionEvent) and len(e.new_unit_info) == 0))
    actions = filter(action_filter, player.events)
    action_index = 0

    for fixation in player.fixations:
      fixation_actions = []
      while action_index < len(actions) and actions[action_index].frame < fixation[1]:
        if actions[action_index].frame >= fixation[0]:
          fixation_actions.append(actions[action_index])
        action_index = action_index + 1

      if len(fixation_actions) > 0:
        action_latencies.append(fixation_actions[0].frame - fixation[0])

    if len(action_latencies) > 0:
      player.action_latency = float(sum(action_latencies)) / len(action_latencies)
    else:
      player.action_latency = None

  if SHOW_SPEED:
    end_time = datetime.now()
    print "PACStats: {} seconds".format((end_time - start_time).total_seconds())

  return replay



