#!/usr/bin/env python

# Python Standard 2.7 Library
import json
import thread

# Third-Party Libraries
import zeroconf
import zmq

#-------------------------------------------------------------------------------
# Remote Control Object Base Class
#-------------------------------------------------------------------------------
context = zmq.Context()

#-------------------------------------------------------------------------------
# RC Server
#-------------------------------------------------------------------------------
def serve(object, name=None):
    name = name or getattr(object, "__name__")
    socket, port = create_socket()
    zeroconf.register(name, "_rc._tcp", port)
    def loop():
        while True:
            data = socket.recv()
            data = json.loads(data)
            if isinstance(data, list):
                function = data.pop(0)
                if data:
                    args = data.pop(0)
                else:
                    args = ()
            else:
                raise ValueError("invalid data")

            function = getattr(object, function)
            try:
                output = [True, function(*args)]
            except Exception as error:
                error_module = type(error).__module__ + "."
                if error_module == "exceptions.":
                    error_module = ""
                error_type = error_module + type(error).__name__
                output = [False, [error_type, error.message]]
            socket.send(json.dumps(output))
    thread.start_new_thread(loop, ())

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
# Tests
#-------------------------------------------------------------------------------
def test(x):
    if x != 42:
        return x+1
    else:
        raise ValueError("42")

