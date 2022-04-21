import pathlib

import pkg_resources

from mopidy import config, ext
from .devicemanager import DeviceManager

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
        schema["name"] = config.String()
        schema["ip"] = config.String()
        schema["frontend"] = config.String()
        return schema

    def setup(self, registry):
        from .actor import MasterFrontend

        self.devicemanager = DeviceManager()
        registry.add("http:app", {"name": self.ext_name, "factory": self.webapp})
        registry.add("frontend", MasterFrontend)

    def get_command(self):
        return None

    def webapp(self, config, core):
        from .web import IndexHandler, MasterApiHandler, MasterApiWebSocketHandler

        return [
            (r"/masterapi/(.+)", MasterApiHandler, {"core": core}),
            (r"/socketapi/(.*)", MasterApiWebSocketHandler, {"core": core}),
            (r"/track/(.+)", IndexHandler, {"core": core}),
        ]

