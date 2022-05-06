import sys
from mopidy.audio import PlaybackState
import logging
from threading import Thread
import asyncio
import concurrent.futures
from tornado import websocket, ioloop
import json
logger = logging.getLogger(__name__)


class DeviceSync():

    def __init__(self, core, ws_url):
        self._core = core
        self.ws_url = ws_url
        self._stop = False
        self.playback_state_future = None
        self._mopidy_ws_opened = False
        self.loop = asyncio.new_event_loop()
        self.loop.set_exception_handler(self.handle_exception)
        asyncio.run_coroutine_threadsafe(self.mopidy_connect(),self.loop)
        self.background_thread = Thread(target=self.start_background_loop, args=(self.loop,), daemon=True)
        self.background_thread.start()
        logger.debug("sync coroutine started")

    def handle_exception(self, loop, context):
      # context["message"] will always be there; but context["exception"] may not
      logger.error(f"LOOP EXCEPTION")
      logger.error(context)
      msg = context.get("exception", context["message"])
      logger.error(f"Caught exception: {msg}")

    def start_background_loop(self, loop: asyncio.AbstractEventLoop) -> None:
       try:
         asyncio.set_event_loop(loop)
         loop.run_forever()
       except Exception:
         logger.error(sys.exc_info())

    def stop(self):
      self._stop = True
      if hasattr(self,'mopidy_ws'):
        if self.mopidy_ws != None:
          self.loop.call_soon_threadsafe(self.mopidy_ws.close)
      logger.debug("stopped sync")

    def cancel_tasks(self):
        logger.debug("get tasks")
        for task in asyncio.all_tasks():
           logger.error(task)
        self.loop.stop()

    def uri_to_master(self, uri):
        params = uri.split(':')
        params.pop(0)
        params.pop(0)
        uri = ":".join(params)
        return uri


    @asyncio.coroutine
    def mopidy_connect(self):
      retries = 0
      max_retries = 1
      while not self._stop:
        logger.debug("mopidy connect")
        try:
          self.mopidy_ws = yield from websocket.websocket_connect(self.ws_url)
          logger.debug("connected to mopidy")
        except:
          logger.error("cannot connect to mopidy")
          retries = retries + 1
          if retries > max_retries:
            logger.error("max retries exceeded, stop sync")
            self.stop()
          if not self._stop:
            yield from asyncio.sleep(10)
        else:
          if not self._stop:
            yield from self.mopidy_run()

    @asyncio.coroutine
    def mopidy_run(self):
      logger.debug("mopidy sync start")
      self._mopidy_ws_opened = True
      self.get_master_tracklist()
      while self._mopidy_ws_opened and not self._stop:
          logger.debug("mopidy sync read messages")
          msg = yield from self.mopidy_ws.read_message()
          logger.debug("mopidy get message")
          if self._stop:
             logger.debug('Skip because stopping')
             return
          if msg is None:
             if self._mopidy_ws_opened:
               self._mopidy_ws_opened = False
               logger.error('connection closed to mopidy')
               self.cancel_futures()
               self.mopidy_ws.close()
               self.mopidy_ws = None
               return
          else:
            data = json.loads(msg)
            if 'event' in data:
              if data['event'] == 'tracklist_changed':
                self.get_master_tracklist()
              elif data['event'] == 'track_playback_started':
                track_uri = self.uri_to_master(data['tl_track']['track']['uri'])
                self.set_current_track(track_uri)
                self.get_playback_state()
              elif data['event'] == 'playback_state_changed':
                self._core.playback.set_state(data['new_state'])
            else:
              if data['id'] == 101: #tracklist
                self._core.tracklist.clear()
                track_uris = []
                for track in data['result']:
                  track_uris.append(self.uri_to_master(track['track']['uri']))
                self._core.tracklist.add(uris=track_uris)
                self.get_current_track()
              elif data['id'] == 102: #currenttrack
                if data['result'] != None:
                  track_uri = self.uri_to_master(data['result']['track']['uri'])
                  self.set_current_track(track_uri)
                  self.get_playback_state()
              elif data['id'] == 103: #playbackstate
                if data['result'] != None:
                  self._core.playback.set_state(data['result'])
                  if self.playback_state_future != None:
                     self.playback_state_future.set_result(data['result'])
                     self.playback_state_future = None
              elif data['id'] == 104: #timeposition
                if data['result'] != None:
                  self._time_position = data['result']
                  self.time_position_future.set_result(self._time_position)

    def cancel_futures(self):
        if self.playback_state_future != None:
          self.playback_state_future.set_result('STOPPED')
          self.playback_state_future = None
          logger.error("playback_state future cancelled")
        if self.time_position_future != None:
          self.time_position_future.set_result(0)
          self.time_position_future = None
          logger.error("time_position future cancelled")

    def write_message(self, payload):
      if self.mopidy_ws != None:
        try:
          self.mopidy_ws.write_message(json.dumps(payload))
        except:
          logger.error('Cannot send ws message')
          logger.error(payload)
          self.cancel_futures()
      else:
        logger.error('Cannot send ws message')
        logger.error(payload)
        self.cancel_futures()

    def get_remote_playback_state(self):
      self.playback_state_future = concurrent.futures.Future()
      self.loop.call_soon_threadsafe(self.wait_playback_state)
      return self.playback_state_future

    def wait_playback_state(self):
      logger.debug("wait_playback_state")
      payload = {
         "method": "core.playback.get_state",
         "jsonrpc": "2.0",
         "params":{},
         "id": 103
      }

    def get_track_position(self):
      self.time_position_future = concurrent.futures.Future()
      self.loop.call_soon_threadsafe(self.wait_track_position)
      return self.time_position_future

    def wait_track_position(self):
      logger.debug("wait_track_position")
      payload = {
         "method": "core.playback.get_time_position",
         "jsonrpc": "2.0",
         "id": 104
      }
      self._time_position = None
      self.write_message(payload)


    def set_current_track(self, uri):
      tl_tracks = self._core.tracklist.filter({"uri": [uri]}).get()
      if len(tl_tracks) > 0:
        #We need to call private method to set current track to replaced one
        self._core._actor.playback._set_current_tl_track(tl_tracks[0])

    def get_master_tracklist(self):
      payload = {
         "method": "core.tracklist.get_tl_tracks",
         "jsonrpc": "2.0",
         "id": 101
      }
      self.write_message(payload)

    def get_current_track(self):
      payload = {
         "method": "core.playback.get_current_tl_track",
         "jsonrpc": "2.0",
         "params":{},
         "id": 102
      }
      self.write_message(payload)

    def get_playback_state(self):
      payload = {
         "method": "core.playback.get_state",
         "jsonrpc": "2.0",
         "params":{},
         "id": 103
      }
      self.write_message(payload)


    def remove_device(self, handler, remove_handler=False):
        if hasattr(handler,'name'):
          if handler.name in self._devices:
            if self._devices[handler.name]['active']:
               self.set_active(self._name)
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


