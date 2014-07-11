"""
Profiles the whole processReplay toolchain including saving to the development
database. It is important to use the dev database because the costs of database
queries are fairly understated when working on a clean database where index
rebuilds are cheap and easy.

Usage:

    python profile.py time test.SC2Replay

Produces all the expected logging output plus a VERY detailed listing of all the
function calls made during processReplay with the following fields:

  ncalls - Number of times called. For recursive calls there will be a X/Y notation
  tottime - Total time spent inside this function excluding time spend in subfunctions
  percall - tottime/ncalls
  cumtime - Total time spent inside this function including time spend in subfunctions
  percall - cumtime/ncalls
  filename:lineno(function) - Place the functionis defined.

"""
import sys
from sc2parse import ggfactory
from sc2parse.sc2reader_to_esdb import SC2ReaderToEsdb
from cStringIO import StringIO

S2ESDB = SC2ReaderToEsdb()

import cProfile, pstats, io

pr = cProfile.Profile(builtins=True)
pr.enable()
replayDB, blob = S2ESDB.processReplay(StringIO(open(sys.argv[2]).read()))
pr.disable()
ps = pstats.Stats(pr)
ps.strip_dirs()
ps.sort_stats(sys.argv[1])
ps.print_stats()
