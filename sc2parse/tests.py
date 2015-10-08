import StringIO
import hashlib
from datetime import datetime

from django.utils import unittest
from django.test import TransactionTestCase
from models import *
from sc2reader_to_esdb import SC2ReaderToEsdb

from sc2parse import ggfactory
import sc2reader
from pprint import pprint
import json

sc2reader.log_utils.log_to_console('INFO')

class SC2ReaderToEsdbTestCase(unittest.TestCase):

    def setUp(self):
        self.sc2reader_to_esdb = SC2ReaderToEsdb()

    def tearDown(self):
        Identity.objects.all().delete()
        IdentityEntity.objects.all().delete()
        Match.objects.all().delete()
        Map.objects.all().delete()
        Replay.objects.all().delete()
        Entity.objects.all().delete()
        MatchSummary.objects.all().delete()
        Graph.objects.all().delete()
        GraphPoint.objects.all().delete()
        PlayerSummary.objects.all().delete()
        Item.objects.all().delete()
        BuildOrder.objects.all().delete()
        BuildOrderItem.objects.all().delete()

    def parse_replay_persist_and_close(self, i):
        replayfile = open("sc2parse/testfiles/replay{replaynum}.SC2Replay".format(replaynum=i), "rb")
        stringio = StringIO.StringIO(replayfile.read())
        replayDB, blob = self.sc2reader_to_esdb.processReplay(stringio, None)
        replayfile.close()
        return Match.objects.all()[0].id, blob

    def get_parsed_replay(self, i):
        replayfile = open("sc2parse/testfiles/replay{replaynum}.SC2Replay".format(replaynum=i), "rb")
        replay = ggfactory.load_replay(replayfile)
        replayfile.close()
        return replay

    def parse_s2gs_persist_and_close(self, i):
        s2gsfile = open("sc2parse/testfiles/s2gs%(s2gsnum)i.s2gs" % {"s2gsnum": i}, "rb")

        s2gsdata = s2gsfile.read()
        stringio = StringIO.StringIO(s2gsdata)
        hash = hashlib.sha256(s2gsdata).hexdigest()
        matchSummaryDB, created = MatchSummary.objects.get_or_create(s2gs_hash = hash)

        self.sc2reader_to_esdb.processSummary(stringio, hash)
        s2gsfile.close()
        return Match.objects.all()[0].id

    def get_parsed_s2gs(self, i):
        s2gsfile = open("sc2parse/testfiles/s2gs%(s2gsnum)i.s2gs" % {"s2gsnum": i}, "rb")
        summary = ggfactory.load_game_summary(s2gsfile)
        s2gsfile.close()
        return summary

    def test_parse_and_dedupe(self):
        """Identities, Replays Matches and Entities are created correctly and de-duping logic works as expected"""
        for i in [1,2,1]:
            self.parse_replay_persist_and_close(i)

        idDBs = Identity.objects.all()
        self.assertEquals(idDBs.count(), 15)
        replayDBs = Replay.objects.all()
        self.assertEquals(replayDBs.count(), 2)
        matchDBs = Match.objects.all()
        self.assertEquals(matchDBs.count(), 2)
        entityDBs = Entity.objects.all()
        self.assertEquals(entityDBs.count(), 16)

    def test_total_army(self):
        replay = self.get_parsed_replay(3)
        ta = replay.players[1].total_army
        self.assertEquals(ta[0], 31)  # i selected 31 of my probes in this game
        self.assertEquals(ta[1], 26)  # i selected 26 of my zealots in this game

    def test_army_minutes(self):
        replay = self.get_parsed_replay(3)
        abm = replay.players[1].army_by_minute
        self.assertEquals(len(abm), 19)  # abm array is a list for minutes 0 through 18, inclusive -- 19 things
        self.assertEquals(abm[1][0], 6)  # my first 6 probes
        self.assertEquals(abm[4][1], 1)  # my first zealot

    def test_parse_army(self):
        """Storing total army data in the DB"""
        self.parse_replay_persist_and_close(3)

        entityDBs = Entity.objects.filter(race__exact="P")
        self.assertEquals(entityDBs.count(), 1)
        entityDB = entityDBs[0]
        self.assertEquals(entityDB.u0, 31)
        self.assertEquals(entityDB.u1, 26)

    def assert_army_minute(self, entityDB, minute, unitnum, expected_count):
        minuteDBs = Minute.objects.filter(entity__exact=entityDB,
                                          minute__exact=minute)
        self.assertEquals(minuteDBs.count(), 1)
        unit_count = getattr(minuteDBs[0], "u{}".format(unitnum))
        self.assertEquals(unit_count, expected_count)

    def test_parse_army_minutes(self):
        """Storing army-by-minute data in the DB"""
        self.parse_replay_persist_and_close(3)

        entityDBs = Entity.objects.filter(race__exact="P")
        self.assertEquals(entityDBs.count(), 1)
        entityDB = entityDBs[0]

        minuteDBs = Minute.objects.filter(entity__exact=entityDB)
        self.assertEquals(minuteDBs.count(), 18)  # we store minutes 1 through 18 inclusive, 18 things

        self.assert_army_minute(entityDB, 1, 0, 6)
        self.assert_army_minute(entityDB, 4, 1, 1)

    def test_map_stuff(self):
        """Parsing map info, storing in DB, retrieving from battle.net, storing in S3"""
        matchId, blob = self.parse_replay_persist_and_close("_ggpyjobs#15")
        matchDB = Match.objects.get(pk=matchId)

        # Regression for ggpyjobs#15
        self.assertEquals(matchDB.map.name, 'Molten Crater')

    def test_wwpm(self):
        replay = self.get_parsed_replay(3)
        wwpm = replay.players[1].wwpm
        self.assertEquals(len(wwpm), 13)  # 13 minutes in which i made at least one worker
        self.assertEquals(wwpm[0], 3)     # made 3 workers in the first minute

#TODO add a test case to confirm that time zone handling is correct in the replay and in the persist/retrieve.

    def test_s2gs_parse(self):
        s2gs = self.get_parsed_s2gs(1)
        s2gs = self.get_parsed_s2gs(4)
        s2gs = self.get_parsed_s2gs(5)
        s2gs = self.get_parsed_s2gs(6)
        s2gs = self.get_parsed_s2gs(7)
        s2gs = self.get_parsed_s2gs(8)
        s2gs = self.get_parsed_s2gs(9)

    def test_s2gs_parse_lioor(self):
        s2gs = self.get_parsed_s2gs(11)

    def test_s2gs_parse_another(self):
        s2gs = self.get_parsed_s2gs(2)

    def test_s2gs_parse_and_persist(self):
        self.parse_s2gs_persist_and_close(1)

        idDBs = Identity.objects.order_by('bnet_id').all()
        matchDBs = Match.objects.all()
        entityDBs = Entity.objects.order_by('identities__bnet_id').all()
        psDBs = PlayerSummary.objects.order_by('entity__identities__bnet_id').all()

        self.assertEquals(idDBs.count(), 2)
        self.assertEquals(idDBs[0].bnet_id, 2188962L)
        self.assertEquals(idDBs[1].bnet_id, 3502513L)

        self.assertEquals(matchDBs.count(), 1)
        self.assertEquals(matchDBs[0].duration_seconds, 1065)
        self.assertEquals(matchDBs[0].winning_team, 2)
        self.assertEquals(matchDBs[0].game_type, '1v1')
        self.assertEquals(matchDBs[0].played_at, datetime.strptime('2012-07-22 21:50:49', '%Y-%m-%d %H:%M:%S'))

        self.assertEquals(entityDBs.count(), 2)
        self.assertEquals(entityDBs[0].match.id, entityDBs[1].match.id)
        expectedEntityDetails = [[1L, u'P', u'P', False, 2188962L, 'B4141E'],
                                 [2L, u'T', u'T', True, 3502513L, '0042FF']
                                 ]
        for i in [0,1]:
            entityDB = entityDBs[i]
            interestingDetails = [entityDB.team,
                                  entityDB.race,
                                  entityDB.chosen_race,
                                  entityDB.win,
                                  entityDB.identities.all()[0].bnet_id,
                                  entityDB.color,
                                  ]
            self.assertEquals(interestingDetails, expectedEntityDetails[i])

        self.assertEquals(psDBs.count(), 2)
        self.assertNotEqual(psDBs[0].entity_id, psDBs[1].entity_id)

        expectedPSDetails = [
            {'killed_unit_count': 54L, 'units_trained': 104L, 'workers_created': 65L, 'resource_collection_rate': 1276L, 'overview': 48725L, 'structures_built': 44L, 'structures_razed_count': 0L, 'average_unspent_resources': 648L, 'units': 23125L, 'structures': 4175L, 'resources': 19425L},
            {'killed_unit_count': 44L, 'units_trained': 171L, 'workers_created': 64L, 'resource_collection_rate': 1706L, 'overview': 67350L, 'structures_built': 54L, 'structures_razed_count': 7L, 'average_unspent_resources': 502L, 'units': 32950L, 'structures': 6825L, 'resources': 25375L}
            ]

        for actual, expected in zip(psDBs, expectedPSDetails):
            for key in expected.keys():
                self.assertEquals(expected[key], getattr(actual, key),
                                  "for {}, expected {} but saw {}".format(key, expected[key], getattr(actual, key)))


    def verifyCondemnedRidgeReplay(self):
        idDBs = Identity.objects.order_by('bnet_id').all()
        matchDBs = Match.objects.all()
        entityDBs = Entity.objects.order_by('identities__bnet_id').all()

        self.assertEquals(idDBs.count(), 2)
        expectedIdentityDetails = [
            {'bnet_id': 60884L, 'name': u'HGsSaito', 'subregion': 2L, 'character_code': None, 'type': u'ESDB::Sc2::Identity', 'gateway': u'us'},
            {'bnet_id': 637188L, 'name': u'Zoulas', 'subregion': 1L, 'character_code': None, 'type': u'ESDB::Sc2::Identity', 'gateway': u'us'}
            ]
        for actual, expected in zip(idDBs, expectedIdentityDetails):
            for key in expected.keys():
                self.assertEquals(expected[key], getattr(actual, key),
                                  "for {}, expected {} but saw {}".format(key, expected[key], getattr(actual, key)))


        self.assertEquals(matchDBs.count(), 1)

        # start time may be off by five seconds -- the replay and the s2gs
        # legitimately differ, and our value may differ depending on
        # which one(s) have been processed
        expected_played_at = datetime.strptime('2012-09-26 02:46:29', '%Y-%m-%d %H:%M:%S')
        seconds_off = matchDBs[0].played_at - expected_played_at
        self.assertLessEqual(abs(seconds_off.total_seconds()), 5)

        # duration may be either 507 or 509 -- the replay and the s2gs
        # legitimately differ, and our value may differ depending on
        # which one(s) have been processed
        self.assertIn(matchDBs[0].duration_seconds, [507, 509])

        self.assertEqual(matchDBs[0].map.name, 'Condemned Ridge')
        self.assertEqual(matchDBs[0].expansion, 0)

        expectedMatchDetails = {'category': u'Ladder', 'average_league': None, 'game_type': u'1v1', 'category': u'Ladder', 'release_string': u'1.5.3.23260', 'winning_team': 1L }
        for key in expectedMatchDetails.keys():
            self.assertEquals(expectedMatchDetails[key], getattr(matchDBs[0], key),
                              "for {}, expected {} but saw {}".format(key, expectedMatchDetails[key], getattr(matchDBs[0], key)))


        self.assertEquals(entityDBs.count(), 2)
        self.assertEquals(entityDBs[0].match.id, entityDBs[1].match.id)
#
# TODO test that the matchblob has expected contents
#
#        self.assertEquals(len(eval(entityDBs[0].armies_by_frame)), 40)
#        self.assertEquals(len(eval(entityDBs[1].armies_by_frame)), 24)
        expectedEntityDetails = [
            {'color': u'0042FF', 'win': False, 'apm': 58.9349112426036, 'u9': 0L, 'u8': 0L, 'u5': 3L, 'u4': 7L, 'u7': 0L, 'u6': 0L, 'u1': 6L, 'u0': 21L, 'u3': 0L, 'u2': 3L, 'u19': 0L, 'u18': 0L, 'u11': 0L, 'u10': 0L, 'u13': 0L, 'u12': 0L, 'u15': 0L, 'chosen_race': u'Z', 'u17': 0L, 'u16': 0L, 'wpm': 1.65029469548134, 'u14': 0L, 'race': u'Z', 'team': 2L, 'race_macro': 0.786885245901639},
            {'color': u'B4141E', 'win': True, 'apm': 46.0903732809430, 'u9': 0L, 'u8': 0L, 'u5': 0L, 'u4': 0L, 'u7': 0L, 'u6': 0L, 'u1': 6L, 'u0': 12L, 'u3': 4L, 'u2': 2L, 'u19': 0L, 'u18': 0L, 'u11': 0L, 'u10': 0L, 'u13': 0L, 'u12': 0L, 'u15': 0L, 'chosen_race': u'P', 'u17': 0L, 'u16': 0L, 'wpm': 2.12180746561886, 'u14': 0L, 'race': u'P', 'team': 1L, 'race_macro': 1.0}
            ]
        for actual, expected in zip(entityDBs, expectedEntityDetails):
            for key in expected.keys():
                self.assertEquals(expected[key], getattr(actual, key),
                                  "for {}, expected {} but saw {}".format(key, expected[key], getattr(actual, key)))



    def verifyCondemnedRidgeSummary(self):
        idDBs = Identity.objects.order_by('bnet_id').all()
        matchDBs = Match.objects.all()
        matchSummaryDBs = MatchSummary.objects.all()
        entityDBs = Entity.objects.order_by('identities__bnet_id').all()
        psDBs = PlayerSummary.objects.order_by('entity__identities__bnet_id').all()

        self.assertEquals(matchSummaryDBs.count(), 1)
        mapfacts = matchSummaryDBs[0].mapfacts
        self.assertEquals(mapfacts.map_name, 'Condemned Ridge')
        self.assertEquals(mapfacts.map_description, 'Your expansion progression on this map is pretty straight forward, but when taking the second expansion, make note of and defend the nearby high ground area.')
        self.assertEquals(mapfacts.map_tileset, 'Xil (Wasteland)')

        self.assertEquals(idDBs.count(), 2)
        self.assertEquals(idDBs[0].bnet_id, 60884)
        self.assertEquals(idDBs[1].bnet_id, 637188)

        self.assertEquals(matchDBs.count(), 1)

        # duration may be either 507 or 509 -- the replay and the s2gs
        # legitimately differ, and our value may differ depending on
        # which one(s) have been processed
        self.assertIn(matchDBs[0].duration_seconds, [507, 509])
        self.assertEquals(matchDBs[0].winning_team, 1)
        self.assertEquals(matchDBs[0].game_type, '1v1')
        self.assertEquals(matchDBs[0].category, 'Ladder')
        self.assertEquals(matchDBs[0].expansion, 0)

        # start time may be off by five seconds -- the replay and the s2gs
        # legitimately differ, and our value may differ depending on
        # which one(s) have been processed
        expected_played_at = datetime.strptime('2012-09-26 02:46:29', '%Y-%m-%d %H:%M:%S')
        seconds_off = matchDBs[0].played_at - expected_played_at
        self.assertLessEqual(abs(seconds_off.total_seconds()), 5)

        self.assertEquals(entityDBs.count(), 2)
        self.assertEquals(entityDBs[0].match.id, entityDBs[1].match.id)
        expectedEntityDetails = [[2L, u'Z', u'Z', False, 60884L],
                                 [1L, u'P', u'P', True, 637188L]
                                 ]
        for i in [0,1]:
            entityDB = entityDBs[i]
            interestingDetails = [entityDB.team,
                                  entityDB.race,
                                  entityDB.chosen_race,
                                  entityDB.win,
                                  entityDB.identities.all()[0].bnet_id
                                  ]
            self.assertEquals(interestingDetails, expectedEntityDetails[i], "entity {}".format(i))

        self.assertEquals(psDBs.count(), 2)
        self.assertNotEqual(psDBs[0].entity_id, psDBs[1].entity_id)

        expectedPSDetails = [
            {'killed_unit_count': 2L, 'units_trained': 47L, 'workers_created': 33L, 'overview': 9650L, 'resource_collection_rate': 689L, 'average_unspent_resources': 377L, 'units': 4175L, 'structures': 1350L, 'structures_razed_count': 2L, 'resources': 4125L, 'structures_built': 8L},
            {'killed_unit_count': 18L, 'units_trained': 31L, 'workers_created': 25L, 'overview': 12275L, 'resource_collection_rate': 668L, 'average_unspent_resources': 337L, 'units': 5900L, 'structures': 1975L, 'structures_razed_count': 3L, 'resources': 4300L, 'structures_built': 14L}
            ]

        for actual, expected in zip(psDBs, expectedPSDetails):
            for key in expected.keys():
                self.assertEquals(expected[key], getattr(actual, key), key)


    # This function exists only to speed the process of creating a
    # detailed testing support function such as
    # verifyCondemnedRidgeReplay()
    def extractReplayDetails(self, blob):
        idDBs = Identity.objects.order_by('bnet_id').all()
        matchDBs = Match.objects.all()
        entityDBs = Entity.objects.order_by('identities__bnet_id').all()

        print idDBs.count()
        for idDB in idDBs:
            pprint(idDB.__dict__)

        print matchDBs.count()
        pprint(matchDBs[0].__dict__)

        print entityDBs.count()
        for entityDB in entityDBs:
            self.assertEquals(entityDBs[0].match.id, entityDB.match.id)
            pprint(entityDB.__dict__)

        theblobfile = open("blobfile.json", "w")
        pprint(blob.keys())
        theblobstr = json.dumps(blob)
        theblobfile.write(theblobstr)
        theblobfile.close()

#        pprint(blob['armies_by_frame'])
#        pprint(blob['macro'])
#        pprint(blob['tmacro'])
#        pprint(blob['pmacro'])
#        pprint(blob['num_bases'])
        # locations and camera are too big and unimportant to worry about here


    # This function exists only to speed the process of creating a
    # detailed testing support function such as
    # verifyCondemnedRidgeSummary()
    def extractSummaryDetails(self):
        idDBs = Identity.objects.order_by('bnet_id').all()
        matchDBs = Match.objects.all()
        entityDBs = Entity.objects.order_by('identities__bnet_id').all()
        psDBs = PlayerSummary.objects.order_by('entity__identities__bnet_id').all()

        print idDBs.count()
        print idDBs[0].bnet_id
        print idDBs[1].bnet_id

        print matchDBs.count()
        print matchDBs[0].duration_seconds
        print matchDBs[0].winning_team
        print matchDBs[0].game_type
        print matchDBs[0].played_at

        print entityDBs.count()
        self.assertEquals(entityDBs[0].match.id, entityDBs[1].match.id)

        for i in [0,1]:
            entityDB = entityDBs[i]
            interestingDetails = [entityDB.team,
                                  entityDB.race,
                                  entityDB.chosen_race,
                                  entityDB.win,
                                  entityDB.identities.all()[0].bnet_id
                                  ]
            print interestingDetails

        self.assertEquals(psDBs.count(), 2)
        self.assertNotEqual(psDBs[0].entity_id, psDBs[1].entity_id)

        expectedPSDetails = [
            {'killed_unit_count': 54L, 'units_trained': 104L, 'workers_created': 65L, 'resource_collection_rate': 1276L, 'overview': 48725L, 'structures_built': 44L, 'structures_razed_count': 0L, 'average_unspent_resources': 648L, 'units': 23125L, 'structures': 4175L, 'resources': 19425L},
            {'killed_unit_count': 44L, 'units_trained': 171L, 'workers_created': 64L, 'resource_collection_rate': 1706L, 'overview': 67350L, 'structures_built': 54L, 'structures_razed_count': 7L, 'average_unspent_resources': 502L, 'units': 32950L, 'structures': 6825L, 'resources': 25375L}
            ]
        for actual, expected in zip(psDBs, expectedPSDetails):
            extracted = {}
            for key in expected.keys():
                extracted[key] = getattr(actual, key)
            print extracted


    def test_s2gs_repeat(self):
        matchID = self.parse_s2gs_persist_and_close(5)
        newMatchID = self.parse_s2gs_persist_and_close(5)
        self.assertEquals(matchID, newMatchID)

        self.verifyCondemnedRidgeSummary()

    def test_custom_s2gs_problems_ignored(self):
        self.parse_s2gs_persist_and_close(8)

        # this s2gs is no longer parsed happily since it is less than two minutes long
        # self.parse_s2gs_persist_and_close(10)

    def test_close_replays(self):
        match5ID, blob = self.parse_replay_persist_and_close(5)
        match6ID, blob = self.parse_replay_persist_and_close(6)
        matchedMatch = self.sc2reader_to_esdb.matchClosestToStartTime(Match.objects.all(), Match.objects.get(pk=match5ID).played_at)
        self.assertEquals(match5ID, matchedMatch.id)

    def test_name_assignment(self):
        match5ID, blob = self.parse_replay_persist_and_close(5)
        ident = Identity.objects.get(name__exact='Zoulas')

        self.assertEquals(ident.name_source, "replay")
        self.assertIsNotNone(ident.name_valid_at)
        nva = ident.name_valid_at

        match3ID, blob = self.parse_replay_persist_and_close(3)
        ident = Identity.objects.get(name__exact='Zoulas')

        # replay 3 is an earlier replay than replay 5.
        # so the name_valid_at must not change when we parse it.
        self.assertEquals(ident.name_source, "replay")
        self.assertEquals(ident.name_valid_at, nva)

    def test_hots_replays(self):
        replay = self.get_parsed_replay(8)
        matchID, blob = self.parse_replay_persist_and_close(13)
        matchDBs = Match.objects.all()
        self.assertEquals(matchDBs[0].expansion, 1)

    def test_lotv_replays(self):
        for replayid in [27,28]:
            replay = self.get_parsed_replay(replayid)
            matchID, blob = self.parse_replay_persist_and_close(replayid)
            matchDBs = Match.objects.all()
            self.assertEquals(matchDBs[0].expansion, 2)

    def test_30_replays(self):
        for replayid in [29,30,31]:
            replay = self.get_parsed_replay(replayid)
            matchID, blob = self.parse_replay_persist_and_close(replayid)
            matchDBs = Match.objects.all()
            self.assertEquals(matchDBs[0].expansion, 1)

    def dont_test_30_weirdness(self):
        replayid = 31
        replay = self.get_parsed_replay(replayid)
        for player in replay.players:
            print("Player {}".format(player))
        matchID, blob = self.parse_replay_persist_and_close(replayid)
        matchDBs = Match.objects.all()
        self.extractReplayDetails(blob)
        self.assertEquals(matchDBs[0].expansion, 1)
        idDBs = Identity.objects.order_by('bnet_id').all()
        entityDBs = Entity.objects.order_by('identities__bnet_id').all()
            
    def test_hots_s2gs(self):
        self.parse_s2gs_persist_and_close(12)
        matchDBs = Match.objects.all()
        self.assertEquals(matchDBs[0].expansion, 1)

    def test_WoL_vs_AI(self):
        matchID, blob = self.parse_replay_persist_and_close(14)

    def test_204_with_clantag(self):
        matchID, blob = self.parse_replay_persist_and_close(15)

    def test_wont_merge_with_different_players(self):
        self.parse_s2gs_persist_and_close(16)
        self.parse_s2gs_persist_and_close(17)
        matchDBs = Match.objects.all()
        self.assertEquals(matchDBs.count(), 2)

    def test_training_match_merges_replay_and_s2gs(self):
        self.parse_s2gs_persist_and_close(18)
        self.parse_replay_persist_and_close(18)
        matchDBs = Match.objects.all()
        self.assertEquals(matchDBs.count(), 1)

    def test_training_match_merges_s2gs_and_replay(self):
        self.parse_replay_persist_and_close(18)
        self.parse_s2gs_persist_and_close(18)
        matchDBs = Match.objects.all()
        self.assertEquals(matchDBs.count(), 1)

#
# These tests were for some replays provided by blizzard that use map
# file URLs not available to the public. We hacked them to work, but
# during the Engine/event refactor, Graylin took the hacks out.
#
#    def test_208_replays(self):
#        matchID, blob = self.parse_replay_persist_and_close(20)
#        matchID, blob = self.parse_replay_persist_and_close(21)
#
#    def test_208_Replay2(self):
#        matchID, blob = self.parse_replay_persist_and_close(22)

    def test_creepspread(self):
      replay = self.get_parsed_replay(24)
      print replay.players[0].creep_spread_by_minute
      print replay.players[0].max_creep_spread
      self.assertEquals(replay.players[0].max_creep_spread, (840, 5.34))

    def test_creepspread_parse(self):
      matchID, blob = self.parse_replay_persist_and_close(25)
      entityDBs = Entity.objects.filter(race__exact="Z")
      self.assertEquals(entityDBs.count(), 1)
      entityDB = entityDBs[0]
      self.assertEquals(entityDB.max_creep_spread, 34.39)

      minuteDBs = Minute.objects.filter(entity__exact=entityDB,
                                        minute__exact=18)
      self.assertEquals(minuteDBs.count(), 1)
      minuteDB = minuteDBs[0]
      self.assertEquals(minuteDB.creep_spread, 31.62)


    # take dont_ away from the following function name to do a
    # 3-replay speed benchmark
    def dont_test_creepspread_speed(self):
      before = datetime.now()
      for repnum in [24,25,26]:
        matchID, blob = self.parse_replay_persist_and_close(repnum)
        
      after = datetime.now()
      print after - before


class SC2ReaderToEsdbPKDependentTestCases(TransactionTestCase):
    reset_sequences = True

    # What is the best way to avoid the duplication of the following three functions with SC2ReaderToEsdbTestCase?
    def setUp(self):
        self.sc2reader_to_esdb = SC2ReaderToEsdb()

    def tearDown(self):
        Identity.objects.all().delete()
        IdentityEntity.objects.all().delete()
        Match.objects.all().delete()
        Map.objects.all().delete()
        Replay.objects.all().delete()
        Entity.objects.all().delete()
        MatchSummary.objects.all().delete()
        Graph.objects.all().delete()
        GraphPoint.objects.all().delete()
        PlayerSummary.objects.all().delete()
        Item.objects.all().delete()
        BuildOrder.objects.all().delete()
        BuildOrderItem.objects.all().delete()

    def parse_replay_persist_and_close(self, i):
        replayfile = open("sc2parse/testfiles/replay{replaynum}.SC2Replay".format(replaynum=i), "rb")
        stringio = StringIO.StringIO(replayfile.read())
        replayDB, blob = self.sc2reader_to_esdb.processReplay(stringio, None)
        replayfile.close()
        return Match.objects.all()[0].id, blob

    def verifyDeadlockRidgeReplay(self, blob):
        idDBs = Identity.objects.order_by('bnet_id').all()
        matchDBs = Match.objects.all()
        entityDBs = Entity.objects.order_by('identities__bnet_id').all()

        self.assertEquals(idDBs.count(), 8)
        expectedIdentityDetails = [
{'bnet_id': 176793L,
 'character_code': None,
 'gateway': u'eu',
 'name': u'moonglow',
 'name_source': u'replay',
 'subregion': 1L,
 'type': u'ESDB::Sc2::Identity'},
{'bnet_id': 310628L,
 'character_code': None,
 'gateway': u'eu',
 'name': u'Kinslayer',
 'name_source': u'replay',
 'subregion': 1L,
 'type': u'ESDB::Sc2::Identity'},
{ 'bnet_id': 439093L,
 'character_code': None,
 'gateway': u'eu',
 'name': u'nodag',
 'name_source': u'replay',
 'subregion': 1L,
 'type': u'ESDB::Sc2::Identity'},
{'bnet_id': 901746L,
 'character_code': None,
 'gateway': u'eu',
 'name': u'Boone',
 'name_source': u'replay',
 'subregion': 1L,
 'type': u'ESDB::Sc2::Identity'},
{ 'bnet_id': 906532L,
 'character_code': None,
 'gateway': u'eu',
 'name': u'Gorvain',
 'name_source': u'replay',
 'subregion': 1L,
 'type': u'ESDB::Sc2::Identity'},
{'bnet_id': 1479009L,
 'character_code': None,
 'gateway': u'eu',
 'name': u'Murmure',
 'name_source': u'replay',
 'subregion': 1L,
 'type': u'ESDB::Sc2::Identity'},
{'bnet_id': 1503115L,
 'character_code': None,
 'gateway': u'eu',
 'name': u'nickyschmitz',
 'name_source': u'replay',
 'subregion': 1L,
 'type': u'ESDB::Sc2::Identity'},
{'bnet_id': 1619043L,
 'character_code': None,
 'gateway': u'eu',
 'name': u'SirJedno',
 'name_source': u'replay',
 'subregion': 1L,
 'type': u'ESDB::Sc2::Identity'},
            ]
        for actual, expected in zip(idDBs, expectedIdentityDetails):
            for key in expected.keys():
                self.assertEquals(expected[key], getattr(actual, key),
                                  "for {}, expected {} but saw {}".format(key, expected[key], getattr(actual, key)))


        self.assertEquals(matchDBs.count(), 1)

        # start time may be off by five seconds -- the replay and the s2gs
        # legitimately differ, and our value may differ depending on
        # which one(s) have been processed
        expected_played_at = datetime.strptime('2013-04-09 20:23:25', '%Y-%m-%d %H:%M:%S')
        seconds_off = matchDBs[0].played_at - expected_played_at
        self.assertLessEqual(abs(seconds_off.total_seconds()), 5)

        self.assertEquals(matchDBs[0].duration_seconds, 2222L)

        self.assertEqual(matchDBs[0].map.name, 'Deadlock Ridge')
        self.assertEqual(matchDBs[0].expansion, 1)

        expectedMatchDetails = {'category': u'Ladder', 'average_league': None, 'game_type': u'4v4', 'category': u'Ladder', 'release_string': u'2.0.7.25293', 'winning_team': 0L }
        for key in expectedMatchDetails.keys():
            self.assertEquals(expectedMatchDetails[key], getattr(matchDBs[0], key),
                              "for {}, expected {} but saw {}".format(key, expectedMatchDetails[key], getattr(matchDBs[0], key)))


        self.assertEquals(entityDBs.count(), 8)
        for entityDB in entityDBs:
            self.assertEquals(entityDBs[0].match.id, entityDB.match.id)

        expectedEntityDetails = [
{ 'apm': 45.972972972973,
 'chosen_race': u'R',
 'color': u'540081',
 'race': u'P',
 'race_macro': 0.473399343974616,
 'team': 1L,
 'u0': 42L,
 'u1': 49L,
 'u10': 0L,
 'u11': 0L,
 'u12': 0L,
 'u13': 0L,
 'u14': 0L,
 'u15': 4L,
 'u16': 0L,
 'u17': 0L,
 'u18': 1L,
 'u19': 0L,
 'u2': 0L,
 'u3': 45L,
 'u4': 0L,
 'u5': 0L,
 'u6': 1L,
 'u7': 4L,
 'u8': 0L,
 'u9': 1L,
 'win': None,
 'wpm': 0.378037803780378},
{'apm': 38.972972972973,
 'chosen_race': u'R',
 'color': u'B4141E',
 'race': u'T',
 'race_macro': 0.793791437845155,
 'team': 1L,
 'u0': 50L,
 'u1': 281L,
 'u10': 0L,
 'u11': 0L,
 'u12': 0L,
 'u13': 1L,
 'u14': 0L,
 'u15': 0L,
 'u16': 0L,
 'u17': 0L,
 'u18': 0L,
 'u19': 0L,
 'u2': 0L,
 'u3': 0L,
 'u4': 0L,
 'u5': 0L,
 'u6': 4L,
 'u7': 0L,
 'u8': 0L,
 'u9': 11L,
 'win': None,
 'wpm': 0.513051305130513},
{'apm': 90.6842105263158,
 'chosen_race': u'R',
 'color': u'0042FF',
 'race': u'Z',
 'race_macro': 0.401901857001884,
 'team': 1L,
 'u0': 84L,
 'u1': 216L,
 'u10': 0L,
 'u11': 3L,
 'u12': 0L,
 'u13': 0L,
 'u14': 4L,
 'u15': 0L,
 'u16': 0L,
 'u17': 0L,
 'u18': 0L,
 'u19': 0L,
 'u2': 3L,
 'u3': 69L,
 'u4': 5L,
 'u5': 28L,
 'u6': 5L,
 'u7': 142L,
 'u8': 1L,
 'u9': 0L,
 'win': None,
 'wpm': 0.945094509450945},
{'apm': 89.6756756756757,
 'chosen_race': u'Z',
 'color': u'1CA7EA',
 'race': u'Z',
 'race_macro': 0.358689560299587,
 'team': 1L,
 'u0': 77L,
 'u1': 239L,
 'u10': 0L,
 'u11': 4L,
 'u12': 0L,
 'u13': 0L,
 'u14': 4L,
 'u15': 0L,
 'u16': 0L,
 'u17': 0L,
 'u18': 0L,
 'u19': 0L,
 'u2': 6L,
 'u3': 31L,
 'u4': 68L,
 'u5': 13L,
 'u6': 6L,
 'u7': 32L,
 'u8': 0L,
 'u9': 0L,
 'win': None,
 'wpm': 0.945094509450945},
{'apm': 70.7297297297297,
 'chosen_race': u'R',
 'color': u'EBE129',
 'race': u'Z',
 'race_macro': 0.392936196338843,
 'team': 2L,
 'u0': 36L,
 'u1': 476L,
 'u10': 0L,
 'u11': 0L,
 'u12': 0L,
 'u13': 0L,
 'u14': 0L,
 'u15': 0L,
 'u16': 0L,
 'u17': 0L,
 'u18': 0L,
 'u19': 0L,
 'u2': 2L,
 'u3': 162L,
 'u4': 0L,
 'u5': 13L,
 'u6': 0L,
 'u7': 0L,
 'u8': 0L,
 'u9': 0L,
 'win': None,
 'wpm': 0.972097209720972},
{'apm': 55.3157894736842,
 'chosen_race': u'R',
 'color': u'168000',
 'race': u'P',
 'race_macro': 0.791410099551384,
 'team': 2L,
 'u0': 58L,
 'u1': 17L,
 'u10': 0L,
 'u11': 0L,
 'u12': 30L,
 'u13': 4L,
 'u14': 0L,
 'u15': 0L,
 'u16': 0L,
 'u17': 4L,
 'u18': 2L,
 'u19': 0L,
 'u2': 2L,
 'u3': 9L,
 'u4': 0L,
 'u5': 0L,
 'u6': 0L,
 'u7': 0L,
 'u8': 0L,
 'u9': 0L,
 'win': None,
 'wpm': 0.972097209720972},
{'apm': 60.1842105263158,
 'chosen_race': u'T',
 'color': u'FE8A0E',
 'race': u'T',
 'race_macro': 0.853350003338606,
 'team': 2L,
 'u0': 42L,
 'u1': 177L,
 'u10': 0L,
 'u11': 0L,
 'u12': 0L,
 'u13': 0L,
 'u14': 0L,
 'u15': 46L,
 'u16': 0L,
 'u17': 0L,
 'u18': 0L,
 'u19': 0L,
 'u2': 1L,
 'u3': 0L,
 'u4': 0L,
 'u5': 0L,
 'u6': 0L,
 'u7': 0L,
 'u8': 0L,
 'u9': 27L,
 'win': None,
 'wpm': 0.621062106210621},
{'apm': 47.2702702702703,
 'chosen_race': u'R',
 'color': u'CCA6FC',
 'race': u'Z',
 'race_macro': 0.484938717996437,
 'team': 2L,
 'u0': 80L,
 'u1': 238L,
 'u10': 40L,
 'u11': 0L,
 'u12': 0L,
 'u13': 0L,
 'u14': 0L,
 'u15': 0L,
 'u16': 33L,
 'u17': 0L,
 'u18': 0L,
 'u19': 0L,
 'u2': 3L,
 'u3': 0L,
 'u4': 11L,
 'u5': 23L,
 'u6': 0L,
 'u7': 0L,
 'u8': 0L,
 'u9': 0L,
 'win': None,
 'wpm': 0.729072907290729},
            ]
        for actual, expected in zip(entityDBs, expectedEntityDetails):
            for key in expected.keys():
                # if key[0]=='u' and expected[key] != 0L:
                #     from sc2parse.plugins import unit_data
                #     print expected['color'], expected['race'], key, unit_data['HotS'][{'Z':'Zerg','T':'Terran','P':'Protoss'}[expected['race']]][int(key[1:])]
                # else:
                #     print expected['color'], expected['race'], key
                self.assertEquals(expected[key], getattr(actual, key),
                                  "for {}, expected {} but saw {}".format(key, expected[key], getattr(actual, key)))

        expectedBlobFile = open("sc2parse/testfiles/blob19.json", "r")
        expectedBlobString = expectedBlobFile.read()
        expectedBlob = json.loads(expectedBlobString)

        actualBlobString = json.dumps(blob)
        actualBlob = json.loads(actualBlobString)

        for key in expectedBlob.keys():
            print "Checking blob's {} entry".format(key)
            if not actualBlob[key] == expectedBlob[key]:
                print "Ooops"
                print "Expected:"
                pprint(expectedBlob[key])
                print "Actual:"
                pprint(actualBlob[key])


    def dont_test_big_4v4_replay(self):
        matchID, blob = self.parse_replay_persist_and_close(19)
        self.verifyDeadlockRidgeReplay(blob)
