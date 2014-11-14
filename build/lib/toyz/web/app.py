"""
web_app.py
Runs the webserver for Toyz
Copyright 2014 by Fred Moolekamp
License: GPLv3
"""

from __future__ import division,print_function
import sys
import platform
import os.path
import shutil
import importlib
import socket

import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import tornado.escape

# Imports from Toyz package
from toyz.utils import core
from toyz.utils import file_access
from toyz.utils.errors import ToyzError, ToyzWebError

tornado.options.define("port", default=None, help="run on the given port", type=int)
tornado.options.define("root_path", default=None, 
    help="Use root_path as the root directory for a Toyz instance")
tornado.options.parse_command_line()

class ToyzHandler(tornado.web.RequestHandler):
    def get_toyz_path(self, path):
        """
        Given a toyz path, return the root path for the 
        """
        toyz_info = path.split('/')
        toy_name = toyz_info[0]
        rel_path = '/'.join(toyz_info[1:])
        user = self.app.users[self.get_user_id()]
    
        if toy_name in user.toyz:
            root, rel_path = os.path.split(user.toyz[toy].full_path)
        else:
            raise tornado.web.HTTPError(404)
            
        full_path = os.path.join(root, path)
        permissions = find_parent_permissions(self.application.db_settings, user, full_path)
        if 'r' in permissions or 'x' in permissions:
            return root, rel_path
        else:
            raise tornado.web.HTTPError(404)
    
    def get_current_user(self):
        """
        Load the name of the current user
        """
        return self.get_secure_cookie("user")
    
    def get_user_id():
        user_id = self.get_current_user().strip('"')
        return user_id

class AuthHandler:
    def get_current_user(self):
        """
        Load the name of the current user
        """
        return self.get_secure_cookie("user")

class ToyzTemplateHandler(ToyzHandler, tornado.web.RequestHandler):
    def initialize(self, **options):
        """
        Initialize handler
        """
        self.options=options
    
    @tornado.web.asynchronous
    def get(self, path):
        self.template_path, rel_path= self.get_toyz_path(path)
        self.render(rel_path)
    
    def get_template_path():
        return self.template_path

class AuthToyzTemplateHandler(AuthHandler, ToyzTemplateHandler):
    @tornado.web.authenticated
    def get(self, path):
        ToyzTemplateHandler.get(self, path)
    

class ToyzStaticFileHandler(ToyzHandler, tornado.web.StaticFileHandler):
    """
    Secure handler for all toyz added to the application. This handles security, such as making sure
    the user has a registered cookie and that the user has acces to the requested files.
    """
    @tornado.web.asynchronous
    def get(self, path):
        self.root, rel_path = self.get_toyz_path(path)
        tornado.web.StaticFileHandler.get(self,rel_path)

class AuthToyzStaticFileHandler(AuthHandler, ToyzStaticFileHandler):
    @tornado.web.authenticated
    def get(self, path):
        ToyzStaticFileHandler.get(self, path)

class AuthStaticFileHandler(AuthHandler, tornado.web.StaticFileHandler):
    @tornado.web.authenticated
    def get(self, path):
        tornado.web.StaticFileHandler.get(self, path)
    
    def validate_absolute_path(self, root, full_path):
        print('root:{0}, full_path:{1}'.format(root, full_path))
        user = self.application.users[self.get_current_user()]
        permissions = find_parent_permissions(self.application.db_settings, user, full_path)
        if 'r' in permissions or 'x' in permissions:
            absolute_path = tornado.web.StaticFileHandler.validate_absolute_path(
                    self, root, full_path)
        else:
            absolute_path = None
        print('Absoulte path:', absolute_path)
        return absolute_path

class AuthLoginHandler(AuthHandler, tornado.web.RequestHandler):
    def initialize(self):
        """
        When the handler is initialized, set the path to the template that needs to be rendered
        """
        self.template_path = os.path.join(core.ROOT_DIR,'web', 'templates')
        
    def get(self):
        """
        Send the login.html page to the client
        """
        try:
            err_msg = self.get_argument('error')
        except:
            err_msg = ''
        self.application.settings['template_path'] = self.template_path
        self.render('login.html', err_msg=err_msg, next=self.get_argument('next'))
    
    def set_current_user(self,user_id):
        """
        Send a secure cookie to the client to keep the user logged into the system
        
        Parameters
        ----------
        userId: string
            - User id of the current user
        
        Returns
        -------
        None
        """
        if user_id:
            self.set_secure_cookie('user',tornado.escape.json_encode(user_id))
        else:
            self.clear_cookie('user')
    
    def post(self):
        """
        Load the userId and password passed to the server from the client and check authentication
        """
        user_id = self.get_argument('user_id',default='')
        pwd = self.get_argument('pwd',default='')
        if core.check_pwd(self.application, user_id, pwd):
            if user_id not in self.application.active_users:
                self.application.active_users[user_id] = self.application.users[user_id]
                print('Users logged in:')
                for user_name, user in self.application.active_users.items():
                    print(user.user_id)
            self.set_current_user(user_id)
            self.redirect(self.get_argument('next',u'/'))
        else:
            redirect = u'/auth/login/?error='
            redirect += tornado.escape.url_escape('Invalid username or password')
            redirect += u'&next='+self.get_argument('next',u'/')
            self.redirect(redirect)


class AuthLogoutHandler(tornado.web.RequestHandler):
    def get(self):
        """
        Clear the users cookie and log them out
        """
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    """
    WebSocketHandler
    
    Websocket that handles jobs sent to the server from clients
    """
    
    def open(self, *args):
        """
        Called when a new websocket is opened
        
        Parameters
        ----------
        *args:
            Currently I don't pass any arguments to this function
        
        Returns
        -------
        None
        """
        user_id=self.get_secure_cookie('user').strip('"')
        self.user = self.application.new_session(user_id, websocket=self)
        #self.user = core.active_users[userId]
        #core.active_users[userId].add_session(websocket=self)

    def on_close(self):
        """
        on_close
        
        on_close is called when the websocket is closed. Eventually this function will delete all temporary
        files being used by the users current session and delete entries in global variables such as
        openSessions, openFits, etc
        
        Parameters
        ----------
        None
        
        Returns
        -------
        None
        """
        user=core.active_users[self.session['userId']]
        del user.openSessions[self.session['sessionId']]
        shutil.rmtree(user.stored_dirs['session'][self.session['sessionId']])
        if len(user.openSessions)==0:
            shutil.rmtree(user.stored_dirs['temp'])
            del core.active_users[self.session['userId']]
        
        print('active users remaining:',core.active_users)
    
    def on_message(self, message):
        """
        on_message
        
        on_message is called when the websocket recieves a message from the client. The user and session information
        is then extracted and processed before running the job initiated by the client.
        
        Parameters
        ----------
        message: JSON unicode string
            - Websockets pass json objects from a client to the server. The input message is the json unicode string
            received by the server from the client that has not yet been decoded.
            - The server expects all messages (after decoding from JSON) to be a dictionary with the following keys:
                id: dictionary
                    - dictionary that contains the following keys:
                        userId: string
                            - Unique identifier of the current user
                        sessionId: string
                            -Unique identifier of the current session
                        requestId: string
                            -Unique identifier for the current request sent by the client
                module: string
                    - Python module that contains the function called by the client
                task: string
                    - Function called by the client
                parameters: dictionary
                    - Dictionary of required and optional parameters passed to the function
                }
        
        Returns
        -------
        None
        """
        #logging.info("message recieved: %r",message)
        decoded=tornado.escape.json_decode(message)
        userId=decoded['id']['userId']
        sessionId=decoded['id']['sessionId']
        
        process_job(decoded)

class MainHandler(ToyzHandler):
    """
    Main Handler when user connects to `localhost:8888/`
    """
    def initialize(self, template_name, template_path):
        """
        Initialize handler
        """
        self.template_name = template_name
        self.template_path = template_path
    
    @tornado.web.asynchronous
    def get(self):
        self.render(self.template_name)
    
    def get_template_path(self):
        return self.template_path

class AuthMainHandler(MainHandler):
    @tornado.web.authenticated
    def get(self):
        MainHandler.get(self)

class ToyzWebApp(tornado.web.Application):
    def __init__(self):
        if tornado.options.options.root_path is not None:
            root_path = core.normalize_path(tornado.options.options.root_path)
        else:
            root_path = tornado.options.options.root_path
        
        self.toyz_settings = core.ToyzSettings(root_path)
        if tornado.options.options.port is not None:
            self.toyz_settings.web.port = tornado.options.options.port
        
        if self.toyz_settings.web.authenticate:
            main_handler = AuthMainHandler
            static_handler = AuthOtherStaticFileHandler
            toyz_static_handler = AuthToyzStaticFileHandler
            toyz_template_handler = AuthToyzTemplateHandler
        else:
            main_handler = MainHandler
            static_handler = tornado.web.StaticFileHandler
            toyz_static_handler = ToyzStaticFileHandler
            toyz_template_handler = ToyzTemplateHandler
        
        self.users = core.load_users(self.toyz_settings)
        self.active_users = {}
        
        if platform.system() == 'Windows':
            file_path = os.path.splitdrive(core.ROOT_DIR)
        else:
            file_path = '/'
        
        handlers = [
            (r"/", main_handler, {
                'template_name': 'home.html',
                'template_path': os.path.join(core.ROOT_DIR, 'web', 'templates')
            }),
            (r"/auth/login/", AuthLoginHandler),
            (r"/auth/logout/", AuthLogoutHandler),
            #(r"/static/(.*)", static_handler, {'path': self.toyz_settings.config.root_path}),
            (r"/file/(.*)", static_handler, {'path': file_path}),
            (r"/toyz/static/(.*)", toyz_static_handler),
            (r"/toyz/template/(.*)", toyz_template_handler),
            (r"/job", WebSocketHandler),
        ]
        
        settings={
            'static_path': core.ROOT_DIR,
            'cookie_secret': self.toyz_settings.web.cookie_secret,
            'login_url':'/auth/login/'
        }
        tornado.web.Application.__init__(self, handlers, **settings)
        
        self.toyz_settings.web.port = self.find_open_port(self.toyz_settings.web.port)
    
    def find_open_port(self, port):
        """
        Begin at `port` and search for an open port on the server
        """
        open_port = port
        try:
            self.listen(port)
        except socket.error:
            open_port = self.find_open_port(port+1)
        return open_port

def init_web_app():
    """
    Run the web application on the server
    """
    print("Server root directory:", core.ROOT_DIR)
    
    # Initialize the tornado web application
    toyz_app = ToyzWebApp()
    print("Application root directory:", toyz_app.toyz_settings.config.root_path)
    
    # Continuous loop to wait for incomming connections
    print("Server is running on port", toyz_app.toyz_settings.web.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    init_web_app()