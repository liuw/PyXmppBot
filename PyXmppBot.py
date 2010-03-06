#!/usr/bin/python
# -*- coding: utf-8 -*-

# XmppBot: A simple jabber/xmpp bot framwork using regular expression patterns
# to dispatch incoming messages.
# Copyright (c) 2010 Wei Liu <liuw@liuw.name>
#
# This code is distributed under GPL/2.0

import sys
import traceback
import xmpp
import urllib
import re
import inspect

'''XmppBot: A very simple jabber/xmpp bot framework

This is a simple jabber/xmpp bot framework using regular expression patterns to
dispatch incoming messages.

Copyright (c) 2010 Wei Liu <liuw@liuw.name>
'''

class XmppBotException(Exception):
    pass

class XmppBotShowException(XmppBotException):
    pass

class XmppBotRegisterHandlerException(XmppBotException):
    pass

XmppShows = ('available', 'offline', 'away', 'busy')

class XmppBot:
    # variables
    connection = None
    show = 'available'
    status = 'XmppBot'
    dispatcher = {}

    def __init__(self,
                 server_host='talk.google.com',
                 server_port=5223,
                 debug=[]):
        self.server_host = server_host
        self.server_port = server_port
        self.debug = debug

    def start(self, login_name, login_passwd):
        jid = xmpp.protocol.JID(login_name)

        user = jid.getNode()
        server = jid.getDomain()

        self.connection = xmpp.Client(server, debug=self.debug)

        conn_res = self.connection.connect(server=(self.server_host,
                                                   self.server_port))

        if not conn_res:
            print >>sys.stderr, 'ERROR: Unable to connect to server %s' % server
            sys.exit(1)
        print >>sys.stderr, 'INFO: connection type is %s' % conn_res

        auth_res = self.connection.auth(user, login_passwd)
        if not auth_res:
            print >>sys.stderr, 'ERROR: Unable to authenticate user %s' % user
            print >>sys.stderr, 'ERROR: %s' % auth_res
            sys.exit(1)
        print >>sys.stderr, 'INFO: authentication type is %s' % auth_res

        self.connection.RegisterHandler('message', self.messageDispatcher)
        self.connection.RegisterHandler('presence', self.presenceHandler)

        self.connection.sendInitPresence()

        self.setState(self.show, self.status)

        self.registerHandler(999, ('.*?(?s)(?m)', self.defaultMessageHandler))

        print >>sys.stderr, 'INFO: Bot started'

        while self.process():
            pass

    def process(self):
        try:
            self.connection.Process(1)
        except KeyboardInterrupt:
            return False
        return True
        
    def presenceHandler(self, connection, presence):
        if presence:
            print '-' * 80
            print presence.getFrom(), ',', presence.getFrom().getResource(), \
                  ',', presence.getType(), ',', presence.getStatus(), ',', \
                  presence.getShow()
            print '~' * 80
            if presence.getType() == 'subscribe':
                jid = presence.getFrom().getStripped()
                self.authorizeJid(jid)

    def authorizeJid(self, jid):
        self.getRoster().Authorize(jid)

    def getRoster(self):
        return self.connection.getRoster()

    def getResources(self, jid):
        roster = self.getRoster()
        if roster is not None:
            return roster.getResources(jid)
        else:
            return None

    def getStatus(self, jid):
        roster = self.getRoster()
        if roster is not None:
            return roster.getResources(jid)
        else:
            return None

    def getShow(self, jid):
        roster = self.getRoster()
        if roster is not None:
            return roster.getShow(jid)
        else:
            return None

    def setState(self, show, status):
        if show:
            show = show.lower()
        if show not in XmppShows:
            raise XmppBotShowException

        self.show = show

        self.status = status

        if self.connection:
            presence = xmpp.Presence(priority=5, show=self.show,
                                      status=self.status)
            self.connection.send(presence)

    def getState(self):
        return self.show, self.status

    def replyMessage(self, recipient, message):
        self.connection.send(xmpp.Message(recipient, message))
    
    def registerHandler(self, priority, rh_pair):
        if type(priority) != int:
            raise XmppBotRegisterHandlerException
        regexp, handler = rh_pair
        try:
            orig = self.dispatcher[priority]
        except KeyError:
            orig = None
        
        # Allow to register method or function as message handler
        if inspect.isfunction(handler) or inspect.ismethod(handler):
            self.dispatcher[priority] = rh_pair
            if orig is not None:
                print >>sys.stderr, 'INFO: Replacing original handler for priority %d' % priority
        else:
            raise XmppBotRegisterHandlerException

    def messageDispatcher(self, connection, message):
        msgbody = message.getBody()
        msgsender = message.getFrom()

        if msgbody:
            msgbody = msgbody.encode('utf-8', 'ignore')
            for k in self.dispatcher.keys():
                regexp, handler = self.dispatcher[k]
                m = re.match(regexp, msgbody)
                if m:
                    try:
                        # match and match only once, if we are about to handle 
                        # sequence of commands, it's better to build a regexp 
                        # tree and register the root of the tree to this
                        # dispatcher, which should be better than simply going
                        # into next match
                        if inspect.ismethod(handler):
                            handler(msgsender, msgbody, m.groups())
                        else:
                            handler(self, msgsender, msgbody, m.groups)
                        break
                    except:
                        self.replyMessage(msgsender, traceback.format_exc())
                
    def defaultMessageHandler(self, msgsender, msgbody, args):
        self.replyMessage(msgsender, msgbody)
