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

def test(x):
    return x+1

def expose(object, name=None):
    name = name or getattr(object, "__name__")
    socket, port = create_socket()
    zeroconf.register(name, "_rc._tcp", port)
    def loop():
        while True:
            data = socket.recv()
            print "data:", data
            data = json.loads(data)
            if isinstance(data, unicode):
                function = data
            elif isinstance(data, list):
                function = data.pop(0)
                if data:
                    args = data.pop(0)
                else:
                    args = ()
                if data:
                    kwargs = data.pop(0)
                else:
                    kwargs = {}
            function = getattr(object, function)
            try:
                output = [True, function(*args, **kwargs)]
            except Exception as error:
                error_module = type(error).__module__ + "."
                if error_module == "exceptions.":
                    error_module == ""
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

