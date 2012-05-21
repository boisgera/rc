#!/usr/bin/env python

# Python Standard 2.7 Library
import json
import thread
from time import time as now

# Third-Party Libraries
import zeroconf
import zmq
import zmq.eventloop.ioloop 

#-------------------------------------------------------------------------------
# Global ZeroMQ Context and Tornado loop  
#-------------------------------------------------------------------------------
context = zmq.Context()
loop = zmq.eventloop.ioloop.IOLoop.instance()

#-------------------------------------------------------------------------------
# RC Server: Request Handler Generation
#-------------------------------------------------------------------------------
def make_request_handler(object, name=None):
    name = name or getattr(object, "__name__")
    socket, port = create_socket()
    # TODO: delay registration until the start of the loop.
    zeroconf.register(name, "_rc._tcp", port)
    def request_handler(*args, **kwargs):
        data = socket.recv()
        data = json.loads(data)
        if isinstance(data, list):
            target = data.pop(0)
            if data:
                args = data.pop(0)
            else:
                args = ()
        else:
            raise ValueError("invalid data")

        output = None
        try:
            attr = getattr(object, target)
            if callable(attr):
                output = [True, attr(*args)]
            elif args == []:
                output = [True, attr]
            elif len(args) == 1:
                setattr(object, target, args[0])
                output = [True, None]
        except Exception as error:
            error_module = type(error).__module__ + "."
            if error_module == "exceptions.":
                error_module = ""
            error_type = error_module + type(error).__name__
            output = [False, [error_type, error.message or ""]]
        socket.send(json.dumps(output))
    return socket, request_handler

def create_socket(ports=None):
    # ports defaults to the range defined by IANA for dynamic or private ports
    ports = ports or range(0xc000, 0xffff + 1) 
    socket = context.socket(zmq.REP)
    for port in ports:
        try:
            socket.bind("tcp://*:{0}".format(port))
            return socket, port
        except zmq.ZMQError as error:
            if error.errno != zmq.EADDRINUSE:
                raise
    else:
        message = "all ports already in use"
        error = zmq.ZMQError(message)
        error.errno = zmq.EADDRINUSE
        raise error

#-------------------------------------------------------------------------------
# RC Client
#-------------------------------------------------------------------------------
def get(name):
    return Proxy(name)

class Function(object):
    def __init__(self, proxy, name):
        self.proxy = proxy
        self.name = name
    def __call__(self, *args):
        return self.proxy([self.name, args])

class Proxy(object):
    def __init__(self, name):
        service_info = zeroconf.search(name, "_rc._tcp").items()[0][1]
        self.socket = context.socket(zmq.REQ)
        self.socket.connect("tcp://{address}:{port}".format(**service_info))
    def __getattr__(self, name):
        return Function(self, name)
    def __call__(self, data):
       data = json.dumps(data)
       self.socket.send(data)
       result = json.loads(self.socket.recv())
       if result[0] is True:
           return result[1]
       else:
           error = result[1]
           message = error[0] + ": " + error[1]
           raise Exception(message)

#-------------------------------------------------------------------------------
# RC Namespace
#-------------------------------------------------------------------------------
class Namespace(object):
    def __getattr__(self, name):
        return get(name)
    def __setattr__(self, name, object):
        socket, handler = make_request_handler(object, name)
        loop.add_handler(socket, handler, loop.READ)
    def __iter__(self):
        for name, type, domain in zeroconf.search(type="_rc._tcp"):
            yield (name, get(name))

objects = Namespace()

#-------------------------------------------------------------------------------
# Tests
#-------------------------------------------------------------------------------
class Timer(object):
    def __init__(self, time=None):
        self._time = time or 0.0
        self._clock = None # None means that the time is frozen

    def get_time(self):
        if self._clock is None:
            return self._time
        else:
            return self._time + (now() - self._clock)
    time = property(get_time)

    def start(self, time=None):
        self._time = time or self._time
        self._clock = now()

    def pause(self):
        self.__init__(time=self.time)

    def stop(self):
        self.__init__()

def test_timer():
    """
    >>> objects.timer = Timer() # server-side
    >>> import time; time.sleep(1.0)
    >>> _ = thread.start_new_thread(loop.start, ())

    >>> timer = objects.timer   # client-side (proxy)
    >>> timer.time()
    0.0
    >>> timer.start()
    >>> t0, t1 = timer.time(), timer.time()
    >>> 0.0 < t0 < t1
    True
    >>> timer.pause()
    >>> t0, t1 = timer.time(), timer.time()
    >>> t0 == t1
    True
    >>> timer.start()
    >>> t1 < timer.time()
    True
    >>> timer.pause()
    >>> timer.start(100.0)
    >>> timer.time() > 100.0
    True
    >>> timer.stop()
    >>> timer.time() == 0.0
    True
    """

def test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    test()

