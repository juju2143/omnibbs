#!/usr/bin/python2
# -*- coding: utf-8 -*-

import logging
import argparse

logging.getLogger('').setLevel(logging.DEBUG)

TELNET_IP_BINDING = '' #all

# Parse the input arguments
# Normally, these would be down in "if __name__ == '__main__'", but we need to know green-vs-threaded for the base class and other imports
parser = argparse.ArgumentParser( description='Run a telnet server.')
parser.add_argument( 'port', metavar="PORT", type=int, help="The port on which to listen on." )
parser.add_argument( '-s', '--ssh', action='store_const', const=True, default=False, help="Run as SSH server using Paramiko library.")
parser.add_argument( '-g', '--green', action='store_const', const=True, default=False, help="Run with cooperative multitasking using Gevent library.")
parser.add_argument( '-e', '--eventlet', action='store_const', const=True, default=False, help="Run with cooperative multitasking using Eventlet library.")
console_args = parser.parse_args()

TELNET_PORT_BINDING = console_args.port

if console_args.ssh:
    SERVERPROTOCOL = 'SSH'
else:
    SERVERPROTOCOL = 'telnet'

if console_args.green:
    SERVERTYPE = 'green'
    # To run a green server, import gevent and the green version of telnetsrv.
    import gevent, gevent.server
    from telnetsrv.green import TelnetHandler, command
elif console_args.eventlet:
    SERVERTYPE = 'eventlet'
    # To run a eventlet server, import eventlet and the eventlet version of telnetsrv.
    import eventlet
    from telnetsrv.evtlet import TelnetHandler, command
else:
    SERVERTYPE = 'threaded'
    # To run a threaded server, import threading and other libraries to help out.
    import SocketServer
    import threading
    import time

    from telnetsrv.threaded import TelnetHandler, command

    # The SocketServer needs *all IPs* to be 0.0.0.0
    if not TELNET_IP_BINDING:
        TELNET_IP_BINDING = '0.0.0.0'

import xmlrpclib
omni = xmlrpclib.ServerProxy("http://www.omnimaga.org/mobiquo/mobiquo.php")

# The TelnetHandler instance is re-created for each connection.
# Therfore, in order to store data between connections, create
# a seperate object to deal with any logic that needs to persist
# after the user logs off.
# Here is a simple example that just counts the number of connections
# as well as the number of times this user has connected.

class MyServer(object):
    '''A simple server class that just keeps track of a connection count.'''
    def __init__(self):
        # Var to track the total connections.
        self.connection_count = 0

        # Dictionary to track individual connections.
        self.user_connect = {}

        self.online_connections = 0

    def new_connection(self, username):
        '''Register a new connection by username, return the count of connections.'''
        self.connection_count += 1
        self.online_connections += 1
        try:
            self.user_connect[username] += 1
        except:
            self.user_connect[username] = 1
        return self.connection_count, self.user_connect[username], self.online_connections

    def del_connection(self):
        '''Removes one to the count of online connections.'''
        self.online_connection -= 1

# Subclass TelnetHandler to add our own commands and to call back
# to myserver.

class TestTelnetHandler(TelnetHandler):
    # Create the instance of the server within the class for easy use
    myserver = MyServer()

    # -- Override items to customize the server --

    #WELCOME = 'You have connected to Omnimaga BBS server v0.0.1-test. This server may frequently restart and crash.'
    WELCOME = ''
    PROMPT = "\x1b[34mσ\x1b[0m> "
    authNeedUser = True
    authNeedPass = True

    color = ""

    omnilogin = None

    def authCallback(self, username, password):
        '''Called to validate the username/password.'''
        if not username:
            self.guest = True
            self.writeline('Guest login is not supported yet')
            raise
        else:
            self.guest = False
            self.writeline('Logging in...')
            self.omnilogin = omni.login(xmlrpclib.Binary(username), xmlrpclib.Binary(password))
            if self.omnilogin["result"] == False:
                self.writeline('Wrong password')
                raise

    def session_start(self):
        '''Called after the user successfully logs in.'''
        #self.writeline('This server is running %s.' % SERVERTYPE)

        # Tell myserver that we have a new connection, and provide the username.
        # We get back the login count information.

        #self.color = self.readline(prompt="Color? [Y/n] ", echo=True, use_history=False)

        globalcount, usercount, onlinecount = self.myserver.new_connection( self.username )

        welcomestr = '''Welcome to
[34m                    ▀                ▄▄▄▄[0m
[34m▄▀▀█▀ █▀▄▀▄ ▀▀█▀█▀ ▀█   █▀▄▀▄ ▄▀▀▄▀ █   █ ▄▀▀▄▀[0m
[34m█  █  █ █ █   █ █   █ ▄ █ █ █ █  █   ▀▀▀█ █  █[0m
[34m ▀▀   ▀ ▀ ▀  ▀  ▀▀   ▀  ▀ ▀ ▀  ▀▀ ▀  ▀▀▀   ▀▀ ▀[0m
              The Coders of Tomorrow since 2001'''

        print("%s connected, type %s" % (self.omnilogin['username'], self.TERM))
        if self.TERM.lower() == 'ansi':
            self.writeline(welcomestr.replace('█', '\xdb').replace('▀', '\xdf').replace('▄', '\xdc'))
            self.PROMPT = "\x1b[34m\xe5\x1b[0m> "
        else:
            self.writeline(welcomestr)

        self.writeline('Welcome back %s! You are connection #%d.' % (self.omnilogin['username'], globalcount))
        #self.writeline('%d users online.' % (onlinecount))
        stats = omni.get_online_users()
        statstr = str(stats['guest_count']) + " guests, " + str(stats['member_count']) + " users: "
        for key in stats['list']:
            statstr = statstr + str(key['user_name']) + ", "
        statstr = statstr[:-2]
        self.writeline(statstr)
        bst = omni.get_board_stat()
        self.writeline("%s members posted %s posts in %s threads" % (bst['total_members'], bst['total_posts'], bst['total_threads']))
        self.writeline('Usertype: %s | Posts: %d' % (self.omnilogin['user_type'], self.omnilogin['post_count']))
        inboxstat = omni.get_inbox_stat()
        if inboxstat['inbox_unread_count'] > 0:
            self.writeline('You have %d new messages.' % (inboxstat['inbox_unread_count']))

        # Track any asyncronous events registered with the timer command
        self.timer_events = []

    def session_end(self):
        '''Called after the user logs off.'''
        #self.myserver.del_connection()
        print("%s disconnected\n" % self.omnilogin['username'])

        # Cancel any pending timer events.  Done a bit different between Greenlets and threads
        if SERVERTYPE == 'green':
            for event in self.timer_events:
                event.kill()

        if SERVERTYPE == 'eventlet':
            for event in self.timer_events:
                event.kill()

        if SERVERTYPE == 'threaded':
            for event in self.timer_events:
                event.cancel()

    def writeerror(self, text):
        '''Called to write any error information (like a mistyped command).
        Add a splash of color using ANSI to render the error text in red.
        see http://en.wikipedia.org/wiki/ANSI_escape_code'''
        TelnetHandler.writeerror(self, "\x1b[91m%s\x1b[0m" % text )


    # -- Custom Commands --
    @command('debug', hidden=True)
    def command_debug(self, params):
        """
        Display some debugging data
        """
        for (v,k) in self.ESCSEQ.items():
            line = '%-10s : ' % (self.KEYS[k], )
            for c in v:
                if ord(c)<32 or ord(c)>126:
                    line = line + curses.ascii.unctrl(c)
                else:
                    line = line + c
            self.writeresponse(line)

    @command('params', hidden=True)
    def command_params(self, params):
        '''[<params>]*
        Echos back the raw received parameters.
        '''
        self.writeresponse("params == %r" % params)

    @command('info')
    def command_info(self, params):
        '''
        Provides some information about the current terminal.
        '''
        self.writeresponse( "Terminal type: %s" % (self.TERM) )
        self.writeresponse( "Command history:" )
        for c in self.history:
            self.writeresponse("  %r" % c)

    @command('timer')
    def command_timer(self, params):
        '''<time> <message>
        In <time> seconds, display <message>.
        Send a message after a delay.
        <time> is in seconds.
        If <message> is more than one word, quotes are required.
        
        example: TIMER 5 "hello world!"
        '''
        try:
            timestr, message = params[:2]
            delay = int(timestr)
        except ValueError:
            self.writeerror( "Need both a time and a message" )
            return
        self.writeresponse("Waiting %d seconds..." % delay)

        if SERVERTYPE == 'green':
            event = gevent.spawn_later(delay, self.writemessage, message)

        if SERVERTYPE == 'eventlet':
            event = eventlet.spawn_after(delay, self.writemessage, message)

        if SERVERTYPE == 'threaded':
            event = threading.Timer(delay, self.writemessage, args=[message])
            event.start()

        # Used by session_end to stop all timer events when the user logs off.
        self.timer_events.append(event)

    @command('passwd', hidden=True)
    def command_set_password(self, params):
        '''[<password>]
        Pretends to set a console password.
        Pretends to set a console password.
        Demonostrates how sensative information may be handled
        '''
        try:
            password = params[0]
        except:
            password = self.readline(prompt="New Password: ", echo=False, use_history=False)
        else:
            # If the password was a parameter, it will have been stored in the history.
            # snip it out to prevent easy snooping
            self.history[-1] = 'passwd'

        password2 = self.readline(prompt="Retype New Password: ", echo=False, use_history=False)
        if password == password2:
            self.writeresponse('Pretending to set new password, but not really.')
        else:
            self.writeerror('Passwords don\'t match.')


    # Older method of defining a command
    # must start with "cmd" and end wtih the command name.
    # Aliases may be attached after the method definitions.
    def cmdECHO(self, params):
        '''<text to echo>
        Echo text back to the console.
        
        '''
        self.writeresponse( ' '.join(params) )
    # Create an alias for this command
    #cmdECHO.aliases = ['REPEAT']


    def cmdTERM(self, params):
        '''
        Hidden command to print the current TERM
        
        '''
        self.writeresponse( self.TERM )
    # Hide this command, old-style syntax.  Will not show in the help list.
    cmdTERM.hidden = True


    @command('hide-me', hidden=True)
    @command(['hide-me-too', 'also-me'])
    def command_do_nothing(self, params):
        '''
        Hidden command to perform no action
        
        '''
        self.writeresponse( 'Nope, did nothing.')

    @command('whoami')
    def command_whoami(self, params):
        '''
        Returns your username.
        
        '''
        self.writeresponse("%s" % self.omnilogin['username'])

    @command('profile')
    def command_profile(self, params):
        '''[<username>]
        Returns profile info.
        
        '''
        user = ' '.join(params)
        if user == '':
            info = omni.get_user_info(xmlrpclib.Binary(self.username))
        else:
            info = omni.get_user_info(xmlrpclib.Binary(' '.join(params)))

        try:
            self.writeresponse("%s" % info['username'])
            self.writeresponse("%s" % info['display_text'])
            self.writeresponse("Posts: %s" % info['post_count'])
            self.writeresponse("Registration time: %s" % info['reg_time'])
            self.writeresponse("Last activity: %s" % info['last_activity_time'])
            self.writeresponse("Online: %s" % info['is_online'])
            for key in info['custom_fields_list']:
                self.writeresponse("%s: %s" % (key['name'], key['value']))
        except:
            self.writeresponse("%s" % info['result_text'])

    @command('viewpost', hidden=True)
    def command_viewpost(self, params):
        self.writeresponse('')

if __name__ == '__main__':

    if SERVERPROTOCOL == 'SSH':
        # Import the SSH stuff
        # If we're using gevent, we have to monkey patch for the paramiko and paramiko_ssh libraries
        if SERVERTYPE == 'green':
            from gevent import monkey; monkey.patch_all()

        if SERVERTYPE == 'eventlet':
            eventlet.monkey_patch(all=True)

        from telnetsrv.paramiko_ssh import SSHHandler, getRsaKeyFile


        # Create the handler for SSH, register the defined handler for use as the PTY
        class TestSSHHandler(SSHHandler):
            telnet_handler = TestTelnetHandler
            # Create or open the server key file
            host_key = getRsaKeyFile("server_rsa.key")

        # Define which handler the server should use:
        Handler = TestSSHHandler
    else:
        Handler = TestTelnetHandler

    if SERVERTYPE == 'green':
        # Multi-green-threaded server
        server = gevent.server.StreamServer((TELNET_IP_BINDING, TELNET_PORT_BINDING), Handler.streamserver_handle)

    if SERVERTYPE == 'eventlet':

        class EvtletStreamServer(object):
            def __init__(self, addr, handle):
                self.ip = addr[0]
                self.port = addr[1]
                self.handle = handle

            def serve_forever(self):
                eventlet.serve(
                    eventlet.listen((self.ip, self.port)),
                    self.handle
                )

        # Multi-eventlet server
        server = EvtletStreamServer(
            (TELNET_IP_BINDING, TELNET_PORT_BINDING),
            Handler.streamserver_handle
        )

    if SERVERTYPE == 'threaded':
        # Single threaded server - only one session at a time
        class TelnetServer(SocketServer.TCPServer):
            allow_reuse_address = True

        server = TelnetServer((TELNET_IP_BINDING, TELNET_PORT_BINDING), Handler)


    logging.info("Starting %s %s server at port %d.  (Ctrl-C to stop)" % (SERVERTYPE, SERVERPROTOCOL, TELNET_PORT_BINDING) )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Server shut down.")
