import logging
import os
import pathlib
import pykka
from mopidy import core
from tornado import gen, web, websocket, httpclient
logger = logging.getLogger(__name__)
import json

from .devicemanager import DeviceManager

class IndexHandler(web.RequestHandler):

    def initialize(self, core):
        self._core = core

    @gen.coroutine
    def get(self, path):
        uri = path
        uri_scheme = path.split(':')[0]
        backends = self._core.playback.backends.get()
        for backend in backends:
          if uri_scheme in backend.uri_schemes.get():
            playback = backend.playback
            if isinstance(playback,pykka.ActorProxy):
               translated = playback.translate_uri(uri).get()
               if translated != None:
                  logger.error(translated)
                  client = httpclient.AsyncHTTPClient(defaults=dict(request_timeout=900))
                  requests = [
                     httpclient.HTTPRequest(url=translated,streaming_callback=self.on_chunk)
                  ]
                  yield list(map(client.fetch,requests))
                  self.finish()
                  return
        self.write('Not found')

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
      logger.error(path)
      if path == 'list':
        self.write(json.dumps(self._devicemanager.get_devices()))
      else:
        self.set_status(404)
        self.write('Not found')


    def post(self, path):
      logger.error(path)
      logger.error(self.request.body)
      if path == 'register':
        data = json.loads(self.request.body)
        self._devicemanager.add_device(data)
        self.set_status(200)
        self.write(json.dumps({'result':'ok'}))
      elif path == 'active':
        data = json.loads(self.request.body)
        self._devicemanager.set_active(data['name'])
        self.set_status(200)
        self.write(json.dumps({'result':'ok'}))
      else:
        self.set_status(404)
        self.write('Not found')


class MasterApiWebSocketHandler(websocket.WebSocketHandler):

    def initialize(self, core):
        self._core = core
        self._devicemanager = DeviceManager()
        self.devices = dict()

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
        self._devicemanager.subscribe(self)

    def device_event(self, devices):
        response = { 'msg': 'devices', 'devices' : devices }
        logger.error(response)
        self.write_message(json.dumps(response))


    def on_message(self, message):
        """
        Message received on channel
        """
        logger.error(message)
        if message == 'list':
          response = { 'msg': 'devices', 'devices' : self._devicemanager.get_devices() }
          logger.error(response)
          self.write_message(json.dumps(response))
        if "activate:" in message:
          params = message.split(':')
          self._devicemanager.set_active(params[1])





