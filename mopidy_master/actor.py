
import pykka

from mopidy import exceptions, listener, zeroconf
from mopidy.core import CoreListener
from mopidy.audio import PlaybackState
from mopidy_mpd import network, session, uri_mapper
from .devicemanager import DeviceManager

import logging
logger = logging.getLogger(__name__)

class MasterFrontend(pykka.ThreadingActor, CoreListener):
    def __init__(self, config, core):
        super(MasterFrontend, self).__init__()
        self.core = core
        self.devicemanager = DeviceManager()
        mst_config = config['master']
        self.devicemanager.configure(core,mst_config['name'],mst_config['ip'],mst_config['frontend'])
        self._name = mst_config['name']

    def on_event(self, event, **kwargs):
         if event == 'track_playback_started':
           self.devicemanager.set_active(self._name)
         logger.error(event)
#        if event not in _CORE_EVENTS_TO_IDLE_SUBSYSTEMS:
#            logger.warning(
#                "Got unexpected event: %s(%s)", event, ", ".join(kwargs)
#            )
#        else:
#            self.send_idle(_CORE_EVENTS_TO_IDLE_SUBSYSTEMS[event])
