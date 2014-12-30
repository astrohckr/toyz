"""
Runs the webapp for Toyz
"""
# Copyright 2014 by Fred Moolekamp
# License: MIT

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
import tornado.gen

# Imports from Toyz package
from toyz.utils import core
from toyz.utils import file_access
import toyz.utils.db as db_utils
from toyz.utils.errors import ToyzError, ToyzWebError

class ToyzHandler(tornado.web.RequestHandler):
    """*Not yet implemented*"""
    def get_toyz_path(self, path):
        """
        Given a toyz path, return the root path for the toy.
        """
        toyz_info = path.split('/')
        toy_name = toyz_info[0]
        rel_path = '/'.join(toyz_info[1:])
        user_toyz = db_utils.get_param(self.application.toyz_settings, 'toyz', 
            user_id=self.get_user_id())
        
        if toy_name in user_toyz:
            root, path = os.path.split(user_toyz[toy])
        else:
            raise tornado.web.HTTPError(404)
            
        permissions = find_parent_permissions(self.application.db_settings, user, path)
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
    """
    Subclass for all secure handlers.
    """
    def get_current_user(self):
        """
        Load the name of the current user
        """
        return self.get_secure_cookie("user")

class ToyzTemplateHandler(ToyzHandler, tornado.web.RequestHandler):
    """* Not yet implemented*"""
    def initialize(self, **options):
        """
        Initialize handler
        """
        self.options=options
    
    @tornado.web.asynchronous
    def get(self, path):
        self.template_path, rel_path=self.get_toyz_path(path)
        self.render(rel_path)
    
    def get_template_path():
        return self.template_path

class AuthToyzTemplateHandler(AuthHandler, ToyzTemplateHandler):
    @tornado.web.authenticated
    def get(self, path):
        ToyzTemplateHandler.get(self, path)
    

class ToyzStaticFileHandler(ToyzHandler, tornado.web.StaticFileHandler):
    """
    Handler for all toyz added to the application.
    """
    @tornado.web.asynchronous
    def get(self, path):
        """
        Called when the application recieves a **get** command from the client.
        """
        self.root, rel_path = self.get_toyz_path(path)
        tornado.web.StaticFileHandler.get(self,rel_path)

class AuthToyzStaticFileHandler(AuthHandler, ToyzStaticFileHandler):
    """
    Secure handler for all toyz added to the application. This handles security, such as making 
    sure the user has a registered cookie and that the user has acces to the requested files.
    """
    @tornado.web.authenticated
    def get(self, path):
        # TODO: Check that user has permissions to access the file
        ToyzStaticFileHandler.get(self, path)

class AuthStaticFileHandler(AuthHandler, tornado.web.StaticFileHandler):
    """
    Handles static files and checks for a secure user cookie and that the user
    has permission to view the file.
    """
    @tornado.web.authenticated
    def get(self, path):
        print('loading', path)
        tornado.web.StaticFileHandler.get(self, path)
    
    def validate_absolute_path(self, root, full_path):
        """
        Check that the user has permission to view the file
        """
        #print('root:{0}, full_path:{1}\n\n'.format(root, full_path))
        permissions = file_access.get_parent_permissions(
            self.application.toyz_settings.db, full_path, 
            user_id=self.get_current_user().strip('"'))
        if 'r' in permissions or 'x' in permissions:
            absolute_path = tornado.web.StaticFileHandler.validate_absolute_path(
                    self, root, full_path)
        else:
            absolute_path = None
        #print('Absoulte path:', absolute_path)
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
            user_id (*string* ): User id of the current user
        """
        if user_id:
            self.set_secure_cookie('user',tornado.escape.json_encode(user_id))
        else:
            self.clear_cookie('user')
    
    def post(self):
        """
        Load the user_id and password passed to the server from the client and 
        check authentication
        """
        user_id = self.get_argument('user_id',default='')
        pwd = self.get_argument('pwd',default='')
        if core.check_pwd(self.application.toyz_settings, user_id, pwd):
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

class WorkspaceHandler(ToyzHandler):
    def initialize(self, ):
        self.template_path = os.path.join(core.ROOT_DIR, 'web', 'templates')
    def get(self, workspace):
        """
        Load the workspace
        """
        print('workspace:', workspace)
        self.render('workspace.html')
    
    def get_template_path(self):
        return self.template_path

class AuthWorkspaceHandler(AuthHandler, WorkspaceHandler):
    @tornado.web.authenticated
    def get(self, workspace):
        WorkspaceHandler.get(self, workspace)
        
class WebSocketHandler(tornado.websocket.WebSocketHandler):
    """
    Websocket that handles jobs sent to the server from clients
    """
    
    def open(self, *args):
        """
        Called when a new websocket is opened
        
        Parameters
            *args: Currently no arguments are passed to this function
        """
        user_id = self.get_secure_cookie('user').strip('"')
        self.application.new_session(user_id, websocket=self)

    def on_close(self):
        """
        Called when the websocket is closed. This function calls the applications
        :py:func:`-toyz.web.app.ToyzWebApp.close_session)` function.
        """
        self.application.close_session(self.session)
    
    def on_message(self, message):
        """
        Called when the websocket recieves a message from the client. 
        The user and session information is then extracted and processed before running the 
        job initiated by the client. Only ``modules`` and ``toyz`` that the user has permission
        to view are accepted, all others return a :py:class:`toyz.utils.errors.ToyzJobError` .
        
        Parameters
            - message (*JSON unicode string* ): see(
              :py:func:`toyz.utils.core.run_job` for the format of the msg)
        
        """
        #logging.info("message recieved: %r",message)
        decoded = tornado.escape.json_decode(message)
        user_id = decoded['id']['user_id']
        if user_id !=self.session['user_id']:
            self.write_message({
                'id':"ERROR",
                'error':"Websocket user does not match task user_id",
                'traceback':''
            })
        session_id = decoded['id']['session_id']
        
        self.application.process_job(decoded)

class MainHandler(ToyzHandler):
    """
    Main Handler when user connects to **localhost:8888/** (or whatever port is used by the
    application).
    """
    def initialize(self, template_name, template_path):
        """
        Initialize handler
        """
        self.template_name = template_name
        self.template_path = template_path
    
    @tornado.web.asynchronous
    def get(self):
        """
        Render the main web page
        """
        self.render(self.template_name)
    
    def get_template_path(self):
        """
        Get the path for the main webpage
        """
        return self.template_path

class AuthMainHandler(MainHandler):
    """
    :py:class:`toyz.web.app.MainHandler` extensions when using secure cookies.
    """
    @tornado.web.authenticated
    def get(self):
        MainHandler.get(self)

from futures import ProcessPoolExecutor

class ToyzWebApp(tornado.web.Application):
    """
    Web application that runs on the server. Along with setting up the Tornado web application,
    it also processes jobs sent to the server from clients.
    """
    def __init__(self):
        """
        Initialize the web application and load saved settings.
        """
        if tornado.options.options.root_path is not None:
            root_path = core.normalize_path(tornado.options.options.root_path)
        else:
            root_path = tornado.options.options.root_path
        
        self.root_path = root_path
        self.toyz_settings = core.ToyzSettings(root_path)
        if tornado.options.options.port is not None:
            self.toyz_settings.web.port = tornado.options.options.port
        
        # If security is enabled, used the secure versions of the handlers
        if self.toyz_settings.security.user_login:
            main_handler = AuthMainHandler
            static_handler = AuthStaticFileHandler
            toyz_static_handler = AuthToyzStaticFileHandler
            toyz_template_handler = AuthToyzTemplateHandler
            workspace_handler = AuthWorkspaceHandler
        else:
            main_handler = MainHandler
            static_handler = tornado.web.StaticFileHandler
            toyz_static_handler = ToyzStaticFileHandler
            toyz_template_handler = ToyzTemplateHandler
            workspace_handler = WorkspaceHandler
        
        self.user_sessions = {}
        
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
            (r"/static/(.*)", static_handler, {'path': core.ROOT_DIR}),
            (r"/workspace/(.*)", workspace_handler),
            (r"/file/(.*)", static_handler, {'path': file_path}),
            (r"/toyz/static/(.*)", toyz_static_handler),
            (r"/toyz/template/(.*)", toyz_template_handler),
            (r"/job", WebSocketHandler),
        ]
        
        settings={
            #'static_path': core.ROOT_DIR,
            'cookie_secret': self.toyz_settings.web.cookie_secret,
            'login_url':'/auth/login/'
        }
        tornado.web.Application.__init__(self, handlers, **settings)
        self.toyz_settings.web.port = self.find_open_port(self.toyz_settings.web.port)
    
    def find_open_port(self, port):
        """
        Begin at ``port`` and search for an open port on the server
        """
        open_port = port
        try:
            self.listen(port)
        except socket.error:
            open_port = self.find_open_port(port+1)
        return open_port
    
    def new_session(self, user_id, websocket):
        """
        Open a new websocket session for a given user
        
        Parameters
            user_id ( :py:class:`toyz.utils.core.ToyzUser` ): User id
            websocket (:py:class:`toyz.web.app.WebSocketHandler` ): new websocket opened
        """
        import datetime
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
            print("Users logged in:", self.user_sessions.keys())
        
        session_id = str(
            datetime.datetime.now()).replace(' ','__').replace('.','-').replace(':','_')
        self.user_sessions[user_id][session_id] = websocket
        shortcuts = db_utils.get_param(self.toyz_settings.db, 'shortcuts', 
            user_id=user_id)
        shortcuts = core.check_user_shortcuts(self.toyz_settings, user_id, shortcuts)
        websocket.session = {
            'user_id': user_id,
            'session_id': session_id,
            'path': os.path.join(shortcuts['temp'], session_id),
        }
        core.create_paths(websocket.session['path'])
        websocket.write_message({
            'id': 'initialize',
            'user_id': user_id,
            'session_id': session_id,
        })
    
    def close_session(self, session):
        """
        Close a websocket session and delete any temporary files or directories
        created during the session. To help ensure all temp files are deleted (in
        case of a server or client error), if the user doesn't have any open session 
        his/her **temp** directory is also deleted.
        """
        shutil.rmtree(session['path'])
        del self.user_sessions[session['user_id']][session['session_id']]
        if len(self.user_sessions[session['user_id']])==0:
            shortcuts = db_utils.get_param(self.toyz_settings.db, 'shortcuts', 
                user_id=session['user_id'])
            shutil.rmtree(shortcuts['temp'])
        
        print('active users remaining:', self.user_sessions.keys())
    
    def process_job(self, msg):
        """
        Currently all jobs are run directly from the web app. Later a job server
        might be implemented that will maintain a queue of long duration jobs, so this 
        function will be used to tag the batch jobs and send them to the job application.
        
        Parameters
            - msg (*dict*): Message sent from web client (see 
              :py:func:`toyz.utils.core.run_job` for the format of the msg)
        """
        if 'batch' in msg:
            # TODO write code to run a batch job, or send it to a batch
            # server
            pass
        else:
            result = self.run_job(msg)
            tornado.ioloop.IOLoop.instance().add_future(result, self.respond)
    
    @tornado.gen.coroutine
    def run_job(self, msg):
        """
        Run a job by opening a new process (possible on a new cpu) and passing the
        job and parameters to the process. This function is actually a generator of a
        `Future()` object, so the exception `tornado.gen.Return` is raised to return
        the result.
        
        In the future this function will be modified to be threaded for certain
        types of web applications, allowing variables to be passed more easily and
        stored in work environments when that type of usage is prefereable.
        
        Parameters
            - msg (*dict*): Message sent from web client (see 
              :py:func:`toyz.utils.core.run_job` for the format of the msg)
            
        Returns
            - result (*future* containing a *dict* ): Message to send back to the user. 
              If there is no response, then ``result={}``
        """
        pool = ProcessPoolExecutor(1)
        result = yield pool.submit(core.run_job, self.toyz_settings, msg)
        pool.shutdown()
        raise tornado.gen.Return(result)
    
    def respond(self, response):
        """
        Once a job has completed, including jobs run by an external job application, 
        send the response to the user. Also, update any objects that need to be updated.
        
        Parameters
            - response (*dict* ): Message to send to the user.
              See :py:func:`toyz.utils.core.run_job` for the format of the msg.
        """
        result = response.result()
        # Check to see if the application has any fields that need to be updated
        if 'update_app' in result:
            for prop in result['update_app']:
                self.update(prop)
            del result['update_app']
        # respond to the client
        if result != {}:
            session = self.user_sessions[result['id']['user_id']][result['id']['session_id']]
            session.write_message(result['response'])
    
    def update(self, attr):
        """
        Certain properties of the application may be changed by an external job,
        for example a user may change his/her password, a new user may be created,
        a setting may be changed, etc. When this happens the job notifies the application
        that something has changed and this function is called to reload the property.
        
        Parameters
            - attr (*string* ): Name of attribute that needs to be updated. So far 
              only **toyz_settings** is supported
        """
        if attr == 'toyz_settings':
            self.toyz_settings = core.ToyzSettings(self.root_path)

def init_web_app():
    """
    Run the web application on the server
    """
    
    # Find any options defined at the command line
    tornado.options.define("port", default=None, help="run on the given port", type=int)
    tornado.options.define("root_path", default=None, 
        help="Use root_path as the root directory for a Toyz instance")
    tornado.options.parse_command_line()
    
    print("Server root directory:", core.ROOT_DIR)
    #print('moduel update', db_utils.param_formats['modules']['update'])
    
    # Initialize the tornado web application
    toyz_app = ToyzWebApp()
    print("Application root directory:", toyz_app.root_path)
    
    # Continuous loop to wait for incomming connections
    print("Server is running on port", toyz_app.toyz_settings.web.port)
    print("Type CTRL-c at any time to quit the application")
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    init_web_app()