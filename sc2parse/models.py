from django.db import models
from datetime import datetime

class Identity(models.Model):
    name = models.CharField(null=True, blank=True, max_length=255, db_index=True, default='')
    gateway = models.CharField(max_length=5, db_index=True)
    subregion = models.IntegerField(db_index=True)
    bnet_id = models.IntegerField(db_index=True)
    character_code = models.IntegerField(null=True, blank=True)
    type = models.CharField(max_length=255, db_index=True, null=False, blank=False)
    name_valid_at = models.DateTimeField(default=datetime.now())  # unlocalized UTC time
    name_source = models.CharField(max_length=16, default="legacy")
    matches_count = models.IntegerField(null=True, blank=True)
    seconds_played_sum = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'esdb_identities'

    def __unicode__(self):
        return '(%d) %s / %s' % (self.id, '' if self.name is None else self.name, self.gateway)


class Map(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    s2ma_hash = models.CharField(max_length=255, null=True, db_index=True)
    gateway = models.CharField(max_length=5, null=True)
    image_scale = models.FloatField(null=True, blank=True)
    transX = models.IntegerField(null=True, blank=True)
    transY = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'esdb_sc2_maps'

    def __unicode__(self):
        return '(%d) %s' % (self.id, self.name)


class Match(models.Model):
    played_at = models.DateTimeField(null=True, db_index=True)  # unlocalized UTC time
    winning_team = models.IntegerField(null=True, blank=True)
    category = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    game_type = models.CharField(max_length=255, db_index=True)
    average_league = models.IntegerField(null=True, blank=True, db_index=True)
    gateway = models.CharField(max_length=3, db_index=True, null=True, blank=True)
    duration_seconds = models.IntegerField(null=True)
    release_string = models.CharField(max_length=255, db_index=True, null=True)
    map = models.ForeignKey('Map', null=True)
    expansion = models.IntegerField(default=0)
    vs_ai = models.IntegerField(null=True)
    ranked = models.IntegerField(null=True)
    cobrand = models.IntegerField(null=True)

    class Meta:
        db_table = 'esdb_matches'


class Replay(models.Model):
    match = models.ForeignKey('Match')
    uploaded_at = models.DateTimeField(null=True, db_index=True)  # unlocalized UTC time
    processed_at = models.DateTimeField(null=True, db_index=True) # unlocalized UTC time
    duration_seconds = models.IntegerField(null=True)
    md5 = models.CharField(max_length=32, db_index=True, null=True)
    hidden = models.IntegerField(default=0)

    class Meta:
        db_table = 'esdb_sc2_match_replays'


class Entity(models.Model):
    match = models.ForeignKey('Match')
    identities = models.ManyToManyField(Identity, through='IdentityEntity')

    win = models.NullBooleanField()
    apm = models.FloatField(null=True)
    wpm = models.FloatField(null=True)
    team = models.IntegerField(null=True, blank=True)
    race = models.CharField(max_length=1, db_index=True)
    chosen_race = models.CharField(max_length=1)
    color = models.CharField(max_length=6, null=True, blank=True)
    race_macro = models.FloatField(null=True)
    max_creep_spread = models.FloatField(null=True)
    action_latency = models.FloatField(null=True)

    u0 = models.IntegerField(null=True)  # number of unit 0 that were ever in the active army
    u1 = models.IntegerField(null=True)
    u2 = models.IntegerField(null=True)
    u3 = models.IntegerField(null=True)
    u4 = models.IntegerField(null=True)
    u5 = models.IntegerField(null=True)
    u6 = models.IntegerField(null=True)
    u7 = models.IntegerField(null=True)
    u8 = models.IntegerField(null=True)
    u9 = models.IntegerField(null=True)
    u10 = models.IntegerField(null=True)
    u11 = models.IntegerField(null=True)
    u12 = models.IntegerField(null=True)
    u13 = models.IntegerField(null=True)
    u14 = models.IntegerField(null=True)
    u15 = models.IntegerField(null=True)
    u16 = models.IntegerField(null=True)
    u17 = models.IntegerField(null=True)
    u18 = models.IntegerField(null=True)
    u19 = models.IntegerField(null=True)

    class Meta:
        db_table = 'esdb_sc2_match_entities'


class Minute(models.Model):
    entity = models.ForeignKey('Entity')
    minute = models.IntegerField()
    apm = models.IntegerField(null=True)
    wpm = models.IntegerField(null=True)
    u0 = models.IntegerField(null=True) # number of unit 0 in the active army at minute:00
    u1 = models.IntegerField(null=True)
    u2 = models.IntegerField(null=True)
    u3 = models.IntegerField(null=True)
    u4 = models.IntegerField(null=True)
    u5 = models.IntegerField(null=True)
    u6 = models.IntegerField(null=True)
    u7 = models.IntegerField(null=True)
    u8 = models.IntegerField(null=True)
    u9 = models.IntegerField(null=True)
    u10 = models.IntegerField(null=True)
    u11 = models.IntegerField(null=True)
    u12 = models.IntegerField(null=True)
    u13 = models.IntegerField(null=True)
    u14 = models.IntegerField(null=True)
    u15 = models.IntegerField(null=True)
    u16 = models.IntegerField(null=True)
    u17 = models.IntegerField(null=True)
    u18 = models.IntegerField(null=True)
    u19 = models.IntegerField(null=True)
    armystrength = models.IntegerField(null=True)
    creep_spread = models.FloatField(null=True)

    class Meta:
        db_table = 'esdb_sc2_match_replay_minutes'


class Provider(models.Model):
    name = models.CharField(max_length=100, db_index=True)

    class Meta:
        db_table = 'esdb_providers'


class ReplayProvider(models.Model):
    replay = models.ForeignKey('Replay')
    provider = models.ForeignKey('Provider')

    class Meta:
        db_table = 'esdb_sc2_match_replay_providers'


class IdentityEntity(models.Model):
    identity = models.ForeignKey('Identity')
    entity = models.ForeignKey('Entity')

    class Meta:
        db_table = 'esdb_identity_entities'


class MatchSummary(models.Model):
    s2gs_hash = models.CharField(max_length=80, db_index=True)

    gateway = models.CharField(max_length=3, db_index=True)
    match = models.ForeignKey('Match', null=True, blank=True)
    mapfacts = models.ForeignKey('MapFacts', null=True, blank=True)

    first_seen_at = models.DateTimeField(null=True, db_index=True)
    processed_at = models.DateTimeField(null=True, db_index=True)
    fetched_at = models.DateTimeField(null=True, db_index=True)

    class Meta:
        db_table = 'esdb_sc2_match_summaries'


class Graph(models.Model):

    class Meta:
        db_table = 'esdb_sc2_match_summary_graph'


class GraphPoint(models.Model):
    graph = models.ForeignKey('Graph')
    graph_seconds = models.IntegerField(null=False, blank=False)
    graph_value = models.IntegerField(null=False, blank=False)

    class Meta:
        db_table = 'esdb_sc2_match_summary_graphpoint'


class PlayerSummary(models.Model):
    entity = models.ForeignKey('Entity')
    build_order = models.ForeignKey('BuildOrder', null=True)
    army_graph = models.ForeignKey('Graph', related_name='+', null=True)
    income_graph = models.ForeignKey('Graph', related_name='+', null=True)
    resources = models.IntegerField(null=True, blank=True)
    units = models.IntegerField(null=True, blank=True)
    structures = models.IntegerField(null=True, blank=True)
    overview = models.IntegerField(null=True, blank=True)
    average_unspent_resources = models.IntegerField(null=True, blank=True)
    resource_collection_rate = models.IntegerField(null=True, blank=True)
    workers_created = models.IntegerField(null=True, blank=True)
    units_trained = models.IntegerField(null=True, blank=True)
    killed_unit_count = models.IntegerField(null=True, blank=True)
    structures_built = models.IntegerField(null=True, blank=True)
    structures_razed_count = models.IntegerField(null=True, blank=True)
    enemies_destroyed = models.IntegerField(null=True, blank=True)
    time_supply_capped = models.IntegerField(null=True, blank=True)
    idle_production_time = models.IntegerField(null=True, blank=True)
    resources_spent = models.IntegerField(null=True, blank=True)
    apm = models.IntegerField(null=True, blank=True)
    upgrade_spending_graph = models.ForeignKey('Graph', related_name='+', null=True)
    workers_active_graph = models.ForeignKey('Graph', related_name='+', null=True)

    class Meta:
        db_table = 'esdb_sc2_match_summary_playersummary'


class Item(models.Model):
    name = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = 'esdb_sc2_match_summary_item'


class BuildOrder(models.Model):

    class Meta:
        db_table = 'esdb_sc2_match_summary_buildorder'


class BuildOrderItem(models.Model):
    build_order = models.ForeignKey('BuildOrder')
    item = models.ForeignKey('Item')
    build_seconds = models.IntegerField(null=False, blank=False)
    supply = models.IntegerField(null=False, blank=False)
    total_supply = models.IntegerField(null=False, blank=False)

    class Meta:
        db_table = 'esdb_sc2_match_summary_buildorderitem'


class MapFacts(models.Model):
    map_name = models.CharField(max_length=100, db_index=True)
    map_description = models.CharField(max_length=1000, db_index=True)
    map_tileset = models.CharField(max_length=100, db_index=True)

    class Meta:
        db_table = 'esdb_sc2_match_summary_mapfacts'

    def __unicode__(self):
        return '(%d) %s: (%s, %s)' % (self.id, self.map_name, self.map_description, self.map_tileset)


class EntityStats(models.Model):
    entity = models.ForeignKey('Entity', primary_key=True)
    highest_league = models.IntegerField(null=True, blank=True)

    # no way to DRY this up as far as I can tell
    # <sob> one point for Ruby
    saturation_1 = models.IntegerField(null=True, blank=True)
    mineral_saturation_1 = models.IntegerField(null=True, blank=True)
    gas_saturation_1 = models.IntegerField(null=True, blank=True)
    worker22x_1 = models.IntegerField(null=True, blank=True)

    base_2 = models.IntegerField(null=True, blank=True)
    miningbase_2 = models.IntegerField(null=True, blank=True)
    saturation_2 = models.IntegerField(null=True, blank=True)
    mineral_saturation_2 = models.IntegerField(null=True, blank=True)
    gas_saturation_2 = models.IntegerField(null=True, blank=True)
    worker22x_2 = models.IntegerField(null=True, blank=True)

    base_3 = models.IntegerField(null=True, blank=True)
    miningbase_3 = models.IntegerField(null=True, blank=True)
    saturation_3 = models.IntegerField(null=True, blank=True)
    mineral_saturation_3 = models.IntegerField(null=True, blank=True)
    gas_saturation_3 = models.IntegerField(null=True, blank=True)
    worker22x_3 = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'esdb_entity_stats'
