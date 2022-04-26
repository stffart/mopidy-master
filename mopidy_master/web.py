import logging
import os
import pathlib
import pykka
from mopidy import core
from tornado import gen, web, websocket, httpclient, httputil
logger = logging.getLogger(__name__)
import json
import asyncio

from .devicemanager import DeviceManager

class IndexHandler(web.RequestHandler):

    def initialize(self, core):
        self._core = core

    @gen.coroutine
    def get(self, path):
        uri = path
        uri_scheme = path.split(':')[0]
        range = self.request.headers.get("Range")
        backends = self._core.playback.backends.get()
        for backend in backends:
          if uri_scheme in backend.uri_schemes.get():
            playback = backend.playback
            if isinstance(playback,pykka.ActorProxy):
               translated = playback.translate_uri(uri).get()
               if translated != None:
                  client = httpclient.AsyncHTTPClient(defaults=dict(request_timeout=900))
                  headers = []
                  if range != None:
                    headers = httputil.HTTPHeaders({"Range":range})
                  requests = [
                     httpclient.HTTPRequest(url=translated,headers=headers,streaming_callback=self.on_chunk,header_callback=self.on_headers)
                  ]

                  yield list(map(client.fetch,requests))
                  self.finish()
                  return
        self.write('Not found')

    def on_headers(self,header):
         params=header.split(': ')
         if len(params) == 2:
           self.set_header(params[0],params[1].replace('\r\n',''))
         if 'HTTP/1.1 206' in header:
           self.set_status(206)

    def on_chunk(self, chunk):
        self.write(chunk)
        self.flush()


class MasterApiHandler(web.RequestHandler):

    def initialize(self, core):
        self._core = core
        self._devicemanager = DeviceManager()
        self.devices = dict()

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def options(self, *args):
        # no body
        # `*args` is for route with `path arguments` supports
        self.set_status(204)
        self.finish()

    def get(self, path):
      if path == 'list':
        self.write(json.dumps(self._devicemanager.get_devices()))
      else:
        self.set_status(404)
        self.write('Not found')


    def post(self, path):
      logger.error(path)
      logger.error(self.request.body)
      self.set_status(404)
      self.write('Not found')


class MasterApiWebSocketHandler(websocket.WebSocketHandler):

    def initialize(self, core):
        self._core = core
        self._devicemanager = DeviceManager()
        self.devices = dict()
        self._is_device = False
        self.closed = False

    @classmethod
    def urls(cls):
        return [
            (r'/ws/', cls, {}),  # Route/Handler/kwargs
        ]


    def open(self, channel):
        """
        Client opens a websocket
        """
        self.channel = channel

    def device_event(self, devices, track_position):
        response = { 'msg': 'devices', 'devices' : devices, 'track_position': track_position }
        logger.debug(response)
        self.loop.call_soon_threadsafe(self.send_event, json.dumps(response))

    def send_event(self, message):
        logger.debug('Sending message to '+self.name)
        self.write_message(message)

    def on_message(self, message):
        """
        Message received on channel
        """
        self.loop = asyncio.get_event_loop()
        try:
          data = json.loads(message)
        except:
          logger.error('bad command received')
          return
        if data['message'] == 'list':
          response = { 'msg': 'devices', 'devices' : self._devicemanager.get_devices(), 'track_position':0 }
          logger.debug(response)
          self.write_message(json.dumps(response))
        if data['message'] == 'activate':
          self._devicemanager.set_active(data['name'])
        if data['message'] == 'subscribe':
          self.name = 'subscriber'
          self._devicemanager.subscribe(self)
        if data['message'] == 'register':
          self._is_device = True
          self.name = data['name']
          self.url = data['url']
          self.ws = data['ws']
          self._devicemanager.add_device(self)


    def on_close(self):
      self.closed = True
      if self._is_device:
         self._devicemanager.remove_device(self,True)

