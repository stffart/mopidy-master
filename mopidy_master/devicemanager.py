
import logging
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

    def configure(self, name, ip, frontend):
        self._devices[name] = {'name':name,'url':f"http://{ip}:6680/mopidy/{frontend}","ws":f"ws://{ip}:6680/mopidy/ws", 'active':False, 'me':True}

    def subscribe(self, handler):
      logger.error('subscribe')
      logger.error(len(self._handlers))
      self._handlers.append(handler);

    def subscribers_event(self):
      n = len(self._handlers)-1
      while n >= 0:
        try:
          logger.error('send to subscriber')
          logger.error(n)
          self._handlers[n].device_event(self._devices)
        except Exception as e:
          logger.error(e)
          #logger.error(f"{type(e).__name__} at line {e.__traceback__.tb_lineno} of {__file__}: {e}")
          self._handlers.pop(n)
        n = n - 1

    def set_active(self, name):
      for device in self._devices:
        if device != name:
           self._devices[device]['active'] = False
      self._devices[name]['active'] = True
      logger.error('set active')
      logger.error(name)
      self.subscribers_event()

    def add_device(self, data):
        self._devices[data['name']] = {
           'name':data['name'],
           'url':data['url'],
           'ws':data['ws'],
           'active':False,
        }
        self.subscribers_event()


    def get_devices(self):
        return self._devices


