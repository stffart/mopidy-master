import logging
import os
import pathlib
import pykka
from mopidy import core
from tornado import gen, web, httpclient
logger = logging.getLogger(__name__)


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
                  logger.debug(translated)
                  client = httpclient.AsyncHTTPClient()
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

