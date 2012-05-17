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
    name = name or getattr(object, "__name__", None)
    if not name:
        raise TypeError("undefined name")
    socket, port = create_socket()
    zeroconf.register(name, "_rc._tcp", port)
    def loop():
        while True:
            data = socket.recv()
            print "data:", data
            data = json.loads(data)
            if isinstance(data, unicode):
                function_name = data
            elif isinstance(data, list):
                function = data.pop(0)
                if data:
                    args = data.pop(0)
                else:
                    args = ()
                if message:
                    kwargs = data.pop(0)
                else:
                    kwargs = {}
            function = getattr(object, function_name)
            output = function(*args, **kwargs)
            socket.send(json.dumps(output)) 
    thread.start_new_thread(loop, ())

def create_socket(ports=None):
    socket = context.socket(zmq.REP)
    # see http://en.wikipedia.org/wiki/Ephemeral_port
    ports = ports or range(49152, 65535+1) #
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

