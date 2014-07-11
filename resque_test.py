import sys, hashlib
from ggtracker import Resque

resque = Resque()

# There is probably more in this dict but this is all
# it seems to need
uid = hashlib.md5(sys.argv[1]).hexdigest()
resque.push('python', {
	'class':'ESDB::Jobs::Sc2::Replay::Parse',
	'args':[uid]
})

# I don't know what goes in here, but it needs to exist
resque.set_status(uid, {'options':dict(file=sys.argv[1])})