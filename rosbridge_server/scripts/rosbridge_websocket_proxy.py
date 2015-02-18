#!/usr/bin/env python
# Software License Agreement (BSD License)
#
# Copyright (c) 2012, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import rospy
import sys
import traceback

from rosauth.srv import Authentication

from signal import signal, SIGINT, SIG_DFL
from functools import partial

from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.websocket import WebSocketHandler

from rosbridge_library.util import json

# Global ID seed for clients
clients_connected = 0
proxy = None
clients = []

class RosbridgeWebSocket(WebSocketHandler):

    def open(self):
        global clients_connected, authenticate, proxy, clients
        clients_connected += 1
        rospy.loginfo("Client connected.  %d clients total.", clients_connected)
        clients.append(self)

    def on_message(self, message):
        global proxy, clients
        try:
            rospy.loginfo("Got message: [%s]", str(message))
            msg = json.loads(message)
            if msg['op'] == 'proxy':
                proxy = self
                rospy.loginfo("It's a proxy!")

            if self == proxy:
                for client in clients:
                    if client != proxy:
                        client.send_message(message)
            else:
                if proxy is not None:
                    proxy.send_message(message)
        except:
            print "Unexpected error:", sys.exc_info()[0]
            traceback.print_exc()

    def on_close(self):
        global clients_connected
        clients_connected = clients_connected - 1
        rospy.loginfo("Client disconnected. %d clients total.", clients_connected)
        if self == proxy:
            proxy = None

    def send_message(self, message):
        IOLoop.instance().add_callback(partial(self.write_message, message))

    def check_origin(self, origin):
        return True

if __name__ == "__main__":
    rospy.init_node("rosbridge_websocket")
    signal(SIGINT, SIG_DFL)

    # SSL options
    certfile = rospy.get_param('~certfile', None)
    keyfile = rospy.get_param('~keyfile', None)
    # if authentication should be used
    authenticate = rospy.get_param('~authenticate', False)
    port = rospy.get_param('~port', 9090)
    address = rospy.get_param('~address', "")

    if "--port" in sys.argv:
        idx = sys.argv.index("--port")+1
        if idx < len(sys.argv):
            port = int(sys.argv[idx])
        else:
            print "--port argument provided without a value."
            sys.exit(-1)

    application = Application([(r"/", RosbridgeWebSocket), (r"", RosbridgeWebSocket)])
    if certfile is not None and keyfile is not None:
        application.listen(port, address, ssl_options={ "certfile": certfile, "keyfile": keyfile})
    else:
        application.listen(port, address)
    rospy.loginfo("Rosbridge WebSocket server started on port %d", port)

    IOLoop.instance().start()
