
from mopidy.audio import PlaybackState
import logging
from threading import Thread
import asyncio
import concurrent.futures
from tornado import websocket, ioloop

from .devicesync import DeviceSync

logger = logging.getLogger(__name__)


class MetaSingleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class DeviceManager(metaclass=MetaSingleton):

    def __init__(self):
        self._devices = dict()
        self._handlers = []
        self.device_sync = None
        self.loop = asyncio.new_event_loop()

    def configure(self, core, name, ip, frontend):
        self._core = core
        self._name = name
        self._devices[name] = {'name':name,'url':f"http://{ip}:6680/mopidy/{frontend}","ws":f"ws://{ip}:6680/mopidy/ws", 'active':False, 'me':True }

    def subscribe(self, handler):
      logger.debug('subscribe new handler')
      if hasattr(handler,'name'):
        logger.debug(handler.name)
      self._handlers.append(handler);
      logger.debug('Total handlers:')
      logger.debug(len(self._handlers))

    def subscribers_event(self):
      n = len(self._handlers)-1
      changed = False
      try:
          track_position = self._core.playback.get_time_position().get()
      except:
          track_position = 0
      while n >= 0:
        if self._handlers[n].closed:
          logger.debug('deleting subscriber')
          self.remove_device(self._handlers[n])
          self._handlers.pop(n)
          changed = True
        else:
          logger.debug('send to subscriber '+self._handlers[n].name)
          self._handlers[n].device_event(self._devices,track_position)
        n = n - 1
      if changed:
        self.subscribers_event()

    def start_replication(self,ws_url):
      if self.device_sync != None:
        if self.device_sync.ws_url != ws_url:
          self.device_sync.stop()
          self.device_sync = DeviceSync(self._core, ws_url)
      else:
          self.device_sync = DeviceSync(self._core, ws_url)

    def stop_replication(self):
      if self.device_sync != None:
        self.device_sync.stop()
        self.device_sync = None

    def set_active(self, name):
      was_active = self._devices[self._name]['active']
      if not was_active and name == self._name: #start playback on activate
        was_any_active = False
        for device in self._devices:
          if self._devices[device]['active']:
             was_any_active = True

        if was_any_active:
          track_position = self.device_sync.get_track_position().result()
          self._core.playback.seek(track_position)
          logger.debug(track_position)

        self.stop_replication()
        logger.error('replication stopped')
        tl_track = self._core.playback.get_current_tl_track().get()
        state = self._core.playback.get_state().get()
        logger.debug("current playback state")
        logger.debug(state)
        if state == PlaybackState.PLAYING:
          self._core.playback.play(tl_track)




      for device in self._devices:
        if device != name:
           self._devices[device]['active'] = False

      self._devices[name]['active'] = True
      logger.debug('set active '+name)
      self.subscribers_event()


      if name != self._name: #pause playback on deactivate
        logger.debug("start replication")
        self.start_replication(self._devices[name]['ws'])
        self._core.playback.pause()

    def remove_device(self, handler, remove_handler=False):
        if hasattr(handler,'name'):
          if handler.name in self._devices:
            if self._devices[handler.name]['active']:
               self.set_active(self._name)
            if handler.name in self._devices:
              del self._devices[handler.name]
          if remove_handler:
            self._handlers.remove(handler)

    def add_device(self, handler):
        self._devices[handler.name] = {
           'name':handler.name,
           'url':handler.url,
           'ws':handler.ws,
           'active':False,
        }
        self.subscribe(handler)
        self.subscribers_event()


    def get_devices(self):
        return self._devices


