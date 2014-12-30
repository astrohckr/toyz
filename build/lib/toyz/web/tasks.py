
# Job tasks sent from web client
# Copyright 2014 by Fred Moolekamp
# License: MIT
"""
While each toy may contain a large number of functions, only the functions located in the
``tasks.py`` file will be callable from the job queue.
"""

from __future__ import print_function, division
import importlib
import os

from toyz.utils import core
from toyz.utils import file_access
from toyz.utils import db as db_utils
from toyz.utils.errors import ToyzJobError

def load_user_settings(toyz_settings, tid, params):
    """
    Load settings for a given user
    
    Parameters
        - toyz_settings ( :py:class:`toyz.utils.core.ToyzSettings`): Settings for the toyz 
          application
        - tid (*string* ): Task ID of the client user running the task
        - params (*dict* ): Any parameters sent by the client (**None** for this function)
    
    Response for all users
        - id: 'user_settings'
        - shortcuts (*dict* ): Dictionary of ``shortcut_name: shortcut_path`` 's for the user
        - workspaces (*dict* ): Dictionary of ``workspace_name: workspace_settings`` for the
          user
    
    Additional response keys for users in the **modify_toyz** group
        - modules (*list* ): List of toyz modules the user can run
        - toyz (*dict* ): Dictionary of ``toy_name: path_to_toy`` 's that the user can run
    
    Additional reponse keys for admins
        - config (*dict* ): Configuration settings for the application
        - db (*dict* ): Database settings
        - web (*dict*): Web settings
        - security (*dict* ): Security settings
        - users (*list* ): list of all users in the database
        - groups (*list* ): list of all groups in the database
        - user_settings (*dict* ): Settings for a specified user (initially the *admin*)
        - group_settings (*dict* ): Settings for a specified group (initially the *admin* group)
    """
    dbs = toyz_settings.db
    old_shortcuts = db_utils.get_param(dbs, 'shortcuts', user_id=tid['user_id'])
    shortcuts = core.check_user_shortcuts(toyz_settings, tid['user_id'], old_shortcuts)
    response = {
        'id':'user_settings',
        'shortcuts': shortcuts,
        'workspaces': db_utils.get_param(dbs, 'workspaces', user_id=tid['user_id'])
    }
    
    groups = db_utils.get_param(toyz_settings.db, 'groups', user_id=tid['user_id'])
    
    # Only allow administrators to modify user settings
    if tid['user_id']=='admin' or 'admin' in groups:
        all_users = db_utils.get_all_ids(dbs, 'user_id')
        all_groups = db_utils.get_all_ids(dbs, 'group_id')
        user_settings = load_user_info(toyz_settings, tid, {
            'user_id': 'admin',
            'user_attr': ['groups', 'modules', 'toyz', 'paths'],
        })
        group_settings = load_user_info(toyz_settings, tid, {
            'group_id': 'admin',
            'user_attr': ['groups', 'modules', 'toyz', 'paths'],
        })
        del user_settings['id']
        del group_settings['id']
        
        user_settings['user_id'] = 'admin'
        group_settings['group_id'] = 'admin'
        response.update({
            'config': toyz_settings.config.__dict__,
            'db': toyz_settings.db.__dict__,
            'web': toyz_settings.web.__dict__,
            'security': toyz_settings.security.__dict__,
            'users': all_users,
            'groups': all_groups,
            'user_settings': user_settings,
            'group_settings': group_settings
        })
    
    # Only allow power users to modify toyz they have access to
    if 'modify_toyz' in groups or 'admin' in groups or tid['user_id'] == 'admin':
        response.update({
            'modules': db_utils.get_param(dbs, 'modules', user_id=tid['user_id']),
            'toyz': db_utils.get_param(dbs, 'toyz', user_id=tid['user_id']),
        })
    
    return response

def load_user_info(toyz_settings, tid, params):
    """
    Load info for a given user from the database
    
    Parameters
        - toyz_settings ( :py:class:`toyz.utils.core.ToyzSettings`): Settings for the toyz 
          application
        - tid (*string* ): Task ID of the client user running the task
        - params (*dict* ): Any parameters sent by the client (see *params* below)
    
    Params
        - user_id or group_id (*string* ): User or group to load parameters for
        - user_attr (*list* ): List of user attributes to load
    
    Response
        - id: 'user_info'
        - Each attribute requested by the client is also returned as a key in the
          response
    """
    user = core.get_user_type(params)
    if 'user_id' in user:
        fields = ['groups', 'paths', 'modules', 'toyz']
    else:
        fields = ['users', 'paths', 'modules', 'toyz']
    
    response = {
        'id': 'user_info'
    }
    for field in fields:
        #print('module update in {0}:'.format(field), db_utils.param_formats['modules']['update'])
        if field in params['user_attr']:
            response[field] = db_utils.get_param(toyz_settings.db, field, **user)
    
    #print('response:', response)
    
    return response

def save_user_info(toyz_settings, tid, params):
    """
    Save a users info. If any admin settings are being changed, ensures that the user
    is in the admin group.
    
    Parameters
        - toyz_settings ( :py:class:`toyz.utils.core.ToyzSettings`): Settings for the toyz 
          application
        - tid (*string* ): Task ID of the client user running the task
        - params (*dict* ): Any parameters sent by the client (see *params* below)
    
    Params can be any settings the user has permission to set on the server.
    
    Response
        - id: 'notification'
        - func: 'save_user_info'
        - msg: 'Settings saved for <user_id>'
    """
    groups = db_utils.get_param(toyz_settings.db, 'groups', user_id=tid['user_id'])
    # check that user is in the admin group
    if 'paths' in params and tid['user_id']!='admin' and 'admin' not in groups:
        raise ToyzJobError("You must be in the admin group to modify path permissions")
    
    if (('modules' in params or 'toyz' in params) and tid['user_id']!='admin' and 
            'admin' not in groups and 'modify_toyz' not in groups):
        raise ToyzJobError(
            "You must be an administrator or belong to the 'modify_toyz' "
            "group to modify a users toyz or module access")
    
    user = core.get_user_type(params)
    update_fields = dict(params)
    if 'user_id' in params:
        del update_fields['user_id']
    elif 'group_id' in params:
        del update_fields['group_id']
    for field in update_fields:
        field_dict = {field: params[field]}
        field_dict.update(user)
        db_utils.update_all_params(toyz_settings.db, field, **field_dict)
    
    if 'user_id' in user:
        msg = params['user_id']
    else:
        msg = params['group_id']
    
    response = {
        'id': 'notification',
        'func': 'save_user_info',
        'msg': 'Settings saved for '+ msg
    }
    
    return response

def add_new_user(toyz_settings, tid, params):
    """
    Add a new user to the toyz application.
    
    Parameters
        - toyz_settings ( :py:class:`toyz.utils.core.ToyzSettings`): Settings for the toyz 
          application
        - tid (*string* ): Task ID of the client user running the task
        - params (*dict* ): Any parameters sent by the client (see *params* below)
    
    Params
        - user_id (*string* ): Id of user to add
    
    Response
        - id: 'notification'
        - func: 'add_new_user'
        - msg: 'User/Group added correctly'
    """
    user = core.get_user_type(params)
    pwd = core.encrypt_pwd(toyz_settings, params['user_id'])
    db_utils.update_param(toyz_settings.db, 'pwd', pwd=pwd, **user)
    if 'user_id' in user:
        msg = 'User added correctly'
    else:
        msg = 'Group added correctly'
    
    response = {
        'id': 'notification',
        'func': 'add_new_user',
        'msg': msg
    }
    return response

def change_pwd(toyz_settings, tid, params):
    """
    Change a users password.
    
    Parameters
        - toyz_settings ( :py:class:`toyz.utils.core.ToyzSettings`): Settings for the toyz 
          application
        - tid (*string* ): Task ID of the client user running the task
        - params (*dict* ): Any parameters sent by the client (see *params* below)
    
    Params
        - current_pwd (*string* ):  Users current password. Must match the password on 
          file or an exception is raised
        - new_pwd (*string* ): New password
        - confirm_pwd (*string* ): Confirmation of the the new password. If new_pwd and 
          confirm_pwd do not match, an exception is raised
    
    Response
        - id: 'notification'
        - func: 'change_pwd'
        - msg: 'Password changed successfully'
    """
    core.check4keys(params, ['current_pwd', 'new_pwd', 'confirm_pwd'])
    if core.check_pwd(toyz_settings, tid['user_id'], params['current_pwd']):
        if params['new_pwd'] == params['confirm_pwd']:
            pwd_hash = core.encrypt_pwd(toyz_settings, params['new_pwd'])
        else:
            raise ToyzJobError("New passwords did not match")
    else:
        raise ToyzJobError("Invalid user_id or password")
    
    db_utils.update_param(toyz_settings.db, 'pwd', user_id=tid['user_id'], pwd=pwd_hash)
    
    response = {
        'id': 'notification',
        'func': 'change_pwd',
        'msg': 'Password changed successfully',
    }
    return response

def load_directory(toyz_settings, tid, params):
    """
    Used by the file browser to load the folders and files in a given path.
    
    Parameters
        - toyz_settings ( :py:class:`toyz.utils.core.ToyzSettings`): Settings for the toyz 
          application
        - tid (*string* ): Task ID of the client user running the task
        - params (*dict* ): Any parameters sent by the client (see *params* below)
    
    Params
        - path (*string* ): Path to search
    
    Response
        - id: 'directory'
        - path (*string* ): path passed to the function
        - shortcuts (*dict* ): Dictionary of ``shortcut_name: shortcut_path`` 's for the user
        - folders (*list* of strings): folders contained in the path
        - files (*list* of strings): files contained in the path
        - parent (*string* ): parent directory of current path
    """
    core.check4keys(params,['path'])
    show_hidden=False
    # If the path is contained in a set of dollar signs (for example `$images$`) then 
    # search in the users shortcuts for the given path
    shortcuts = db_utils.get_param(toyz_settings.db, 'shortcuts', user_id=tid['user_id'])
    if params['path'][0]=='$' and params['path'][-1]=='$':
        shortcut = params['path'][1:-1]
        if shortcut not in shortcuts:
            raise ToyzJobError("Shortcut '{0}' not found for user {1}".format(shortcut, 
                tid['user_id']))
        params['path'] = shortcuts[shortcut]
    
    if not os.path.isdir(params['path']):
        parent = os.path.dirname(params['path'])
        if not os.path.isdir(parent):
            raise ToyzJobError("Path '{0}' not found".format(params['path']))
        params['path'] = parent
    if 'show_hidden' in params and params['show_hidden']:
        show_hidden=True
    
    # Keep separate lists of the files and directories for the current path.
    # Only include the files and directories the user has permissions to view
    files = []
    folders = []
    groups = db_utils.get_param(toyz_settings.db, 'groups', user_id=tid['user_id'])
    if 'admin' in groups or tid['user_id'] == 'admin':
        admin=True
    else:
        admin=False
    for f in os.listdir(params['path']):
        if(f[0]!='.' or show_hidden):
            f_path =os.path.join(params['path'],f)
            if admin:
                permission = True
            else:
                permissions = file_access.get_parent_permissions(toyz_settings.db,
                    f_path, user_id=tid['user_id'])
                if permissions is None:
                    permissions = ''
                permission = 'f' in permissions
            if permission:
                if os.path.isfile(f_path):
                    files.append(str(f))
                elif os.path.isdir(f_path):
                    folders.append(str(f))
            else:
                print("no access to", f)
    files.sort(key=lambda v: v.lower())
    folders.sort(key=lambda v: v.lower())
    response={
        'id': 'directory',
        'path': os.path.join(params['path'],''),
        'shortcuts': shortcuts.keys(),
        'folders': folders,
        'files': files,
        'parent': os.path.abspath(os.path.join(params['path'],os.pardir))
    }
    
    #print('path info:', response)
    return response

def create_dir(app, id, params):
    """
    Creates a new path on the server (if it does not already exist).
    
    Parameters
        - toyz_settings ( :py:class:`toyz.utils.core.ToyzSettings`): Settings for the toyz 
          application
        - tid (*string* ): Task ID of the client user running the task
        - params (*dict* ): Any parameters sent by the client (see *params* below)
    
    Params
        - path (*string* ): path to create on the server
    
    Response
        id: 'create_folder',
        status (*string* ): 'success',
        path (*string* ): path created on the server
    """
    core.create_dirs(params['path'])
    response = {
        'id': 'create folder',
        'status': 'success',
        'path': params['path']
    }
    return response

def get_io_info(app, id, params):
    """
    Get I/O settings for different packages (pure python, numpy, pandas, etc)
    """
    import toyz.utils.io as io
    
    param_sets = {}
    for key, val in io.io_modules.items():
        param_sets[key] = {
            'type': 'div',
            'params': {
                'all': {
                    'type': 'div',
                    'params': val['all']
                },
                'file_types': {
                    'type': 'conditional',
                    'selector': {
                        'file_type': {
                            'lbl': 'file type',
                            'type': 'select',
                            'options': val['file_types'].keys()
                        }
                    },
                    'paramSets': val['file_types']
                }
            }
        }
    
    info = {
        'type': 'div',
        'params': {
            'io_info': {
                'type': 'conditional',
                'selector': {
                    'io_module': {
                        'type': 'select',
                        'lbl': 'I/O module to use',
                        'options': io.io_modules.keys()
                    }
                },
                'paramSets': param_sets
            }
        }
    }
    
    response = {
        'id': 'io_info',
        'io_info': info
    }
    
    return response

def load_data_file(app, id, params):
    """
    Load a data file given a set of parameters from the browser, initialized by
    ``get_io_info``.
    """
    import toyz.utils.io as io
    
    columns, data = io.load_data_file(
        params['io_module'],
        params['file_type'], 
        params['file_options'])
    
    response = {
        'id': 'data_file',
        'columns': columns,
        'data': data
    }
    
    return response