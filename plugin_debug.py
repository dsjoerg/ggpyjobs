from pprint import PrettyPrinter
pprint = PrettyPrinter(indent=2).pprint

import sys, sc2reader
import json
from sc2parse import ggfactory
sc2reader.log_utils.log_to_console('INFO')

for filename in sys.argv[1:]:
    try:
        if True or replay.category == 'Ladder':
            replay = ggfactory.load_replay(filename, verbose=True, load_level=4)
            for player in replay.players:
                print player
                for base in player.bases:
                    print base, base.location
                    print "  Ordered at",divmod(base.ordered_at/16,60)
                    if base.started_at != None:
                        print "  Started at",divmod(base.started_at/16,60)
                    else:
                        print "  Start time unknown"
                    print "  Confirmed at",divmod(base.confirmed_at/16,60)
                    if base.finished_at != None:
                        print "  Finished at",divmod(base.finished_at/16,60)
                    else:
                        print "  Unfinished"
                    print
                print "\n\n"
            # if not [u for u in replay.objects.values() if u.name=='Hive']: continue
            # print replay.map_name, replay.length, replay.start_time
            # for player in replay.players:
            #     if player.play_race != 'Zerg':
            #         continue
            #     print player, player.race_macro
            #     print player.hatches
            #     for hatch in player.macro_hatches.values():
            #         print hatch
            #         print "  First Activity {0:02}:{1:02}".format(*divmod(hatch.first_activity/16,60))
            #         print "  Last Activity: {0:02}:{1:02}".format(*divmod(hatch.last_activity/16,60))
            #         print "  Utilization: {0:.2f}%".format(hatch.utilization)
            #         print "  Inject Time: {0}".format(hatch.inject_time)
            #         print "  Active Time: {0}".format(hatch.active_time)
            #         print "  Times: ", ', '.join(str(divmod(i/16,60)) for i in hatch.injects)
            #     print

        else:
            print "Skipped {} game {}; {}".format(replay.category, replay.map_name, filename)

    except Exception as e:
        raise
        #print "[FATAL] {}\n{}".format(filename, str(e))
