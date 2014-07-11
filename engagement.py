import sys
import sc2reader
from sc2parse import ggfactory

# usage GGFACTORY_CACHE_DIR=testcache python engagement.py <ggtracker match id>

replay = ggfactory.load_replay("http://ggtracker.com/matches/{}/replay".format(sys.argv[1]))
