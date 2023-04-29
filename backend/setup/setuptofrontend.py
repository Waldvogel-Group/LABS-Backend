import re
import json

from twisted.web import http
from twisted.web.server import NOT_DONE_YET
from twisted.internet import defer
from twisted.python import failure
from twisted.logger import Logger

log = Logger()

class SetupHandledRequest(http.Request):
    def process(self):
        pathmatch = re.match(r"/api/(?P<function>.+)", self.path.decode())
        setup = self.channel.factory.setup
        self.setHeader('Content-Type', 'text/html')
        try:
            handler = getattr(setup, f"remote_{pathmatch.group('function')}")
        except AttributeError:
            self.setResponseCode(http.NOT_IMPLEMENTED)
            self.write(b"Not Found. Sorry, no such function.")
            self.finish()
        else:
            kwargs = {}
            for key, value in self.args.items():
                value = value[0].decode()
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError:
                    pass
                kwargs[key.decode()] = value
            d = defer.maybeDeferred(handler, **kwargs)
            d.addCallbacks(self.delayed_response, self.delayed_failure)
            return NOT_DONE_YET

    def delayed_response(self, result):
        self.write(json.dumps(result).encode())
        self.finish()
        return result

    def delayed_failure(self, error: failure.Failure):
        log.error(str(error.value))
        self.setResponseCode(http.INTERNAL_SERVER_ERROR)
        self.write(str(error.value).encode())
        self.finish()
        raise error


class SetupChannel(http.HTTPChannel):
    requestFactory = SetupHandledRequest


class SetupChannelFactory(http.HTTPFactory):
    protocol = SetupChannel

    def __init__(self, setup, *args, **kwargs):
        self.setup = setup
        super().__init__(*args, **kwargs)