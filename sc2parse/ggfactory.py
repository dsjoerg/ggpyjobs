import os
import sc2reader

from sc2reader.factories.plugins.replay import APMTracker, SelectionTracker
from sc2parse.plugins import WWPMTracker, TrainingTracker, ActivityTracker, OwnershipTracker, LifeSpanTracker, ArmyTracker, ZergMacroTracker, BaseTracker, ProtossTerranMacroTracker, EngagementTracker, MiningBaseIdentifier, MapFileDepotFixer, ScoutingTracker, UpgradesTracker
from sc2parse.skillcraft import ScreenFixationIDT, PACStats
from sc2reader import engine
from sc2reader.engine.plugins import CreepTracker
#from sc2reader.engine.plugins import CreepTracker, HotkeyCount

FRAMES_PER_SECOND = 16
sc2reader.log_utils.log_to_console('INFO')

class GGFactory(sc2reader.factories.DoubleCachedSC2Factory):
    def __init__(self, cache_dir, max_cache_size=0, **options):
        """cache_dir must be an absolute path, max_cache_size=0 => unlimited"""
        if not cache_dir:
            raise ValueError("cache_dir is now required.")

        super(GGFactory, self).__init__(cache_dir, max_cache_size, **options)

        # Register all the replay plugins; order matters!
        self.register_plugin('Replay',APMTracker())
        self.register_plugin('Replay',SelectionTracker())
        self.register_plugin('Replay',WWPMTracker(ww_length_frames=3 * FRAMES_PER_SECOND))
        self.register_plugin('Replay',TrainingTracker())
        self.register_plugin('Replay',UpgradesTracker())

        # These require Selection Tracking
        self.register_plugin('Replay',ActivityTracker())
        self.register_plugin('Replay',OwnershipTracker())

        #Also requires Training and Ownership Tracking
        self.register_plugin('Replay',LifeSpanTracker())
        self.register_plugin('Replay',ArmyTracker())

        # Requires Selection and Activity Tracking
        self.register_plugin('Replay',BaseTracker())
        self.register_plugin('Replay',ZergMacroTracker())
        self.register_plugin('Replay',ProtossTerranMacroTracker())
        self.register_plugin('Replay',MapFileDepotFixer())
        self.register_plugin('Replay',MiningBaseIdentifier())
        self.register_plugin('Replay',EngagementTracker())

        # Requires Base Tracking
        self.register_plugin('Replay',ScoutingTracker())

        # Skillcraft plugins; order matters
        self.register_plugin('Replay',ScreenFixationIDT())
        self.register_plugin('Replay',PACStats())



# The cache_dir is where remote files get cached to avoid
# expensive and repetitive lookups. This is optional.
CACHE_DIR = os.environ.get('GGFACTORY_CACHE_DIR',None)
CACHE_SIZE = int(os.environ.get('GGFACTORY_CACHE_SIZE',100))

# Expose a nice module level interface
__defaultFactory = GGFactory(cache_dir=CACHE_DIR, max_cache_size=CACHE_SIZE)

load = __defaultFactory.load
load_all = __defaultFactory.load_all
load_replays = __defaultFactory.load_replays
load_replay = __defaultFactory.load_replay
load_maps = __defaultFactory.load_maps
load_map = __defaultFactory.load_map
load_game_summaries = __defaultFactory.load_game_summaries
load_game_summary = __defaultFactory.load_game_summary
load_localizations = __defaultFactory.load_localizations
load_localization = __defaultFactory.load_localization

reset = __defaultFactory.reset
configure = __defaultFactory.configure
register_plugin = __defaultFactory.register_plugin

engine.register_plugins(CreepTracker())

