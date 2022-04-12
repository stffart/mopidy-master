import pathlib

import pkg_resources

from mopidy import config, ext

__version__ = pkg_resources.get_distribution("Mopidy-Master").version
import logging
logger = logging.getLogger(__name__)

class Extension(ext.Extension):

    dist_name = "Mopidy-Master"
    ext_name = "master"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        return schema

    def setup(self, registry):
        registry.add("http:app", {"name": self.ext_name, "factory": self.webapp})

    def get_command(self):
        return None

    def webapp(self, config, core):
        from .web import IndexHandler

        return [
            (r"/(.+)", IndexHandler, {"core": core}),
        ]

