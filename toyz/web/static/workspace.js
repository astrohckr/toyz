// Workspace utilities
// Copyright 2014 by Fred Moolekamp
// License: MIT

Toyz.namespace('Toyz.Workspace');

Toyz.Workspace.load_api_dependencies = function(tile_api, namespace, url, callback){
    if(!Toyz.Core.exists(namespace) || 
            !Toyz.Core.get_var(namespace).dependencies_loaded()){
        Toyz.Core.load_dependencies(
            dependencies={
                js: [url]
            }, 
            callback = function(ns, callback){
                var namespace = Toyz.Core.get_var(ns);
                namespace.load_dependencies(callback);
            }.bind(null, namespace, callback)
        );
    }else{
        callback();
    };
};

Toyz.Workspace.contextMenu_items = function(workspace){
    var items = {
        "new": {
            name: "new",
            items: {
                "tile": {name: "tile", callback: workspace.new_tile},
                "source": {name: "source", callback: function(){
                    workspace.data_sources.editing = '';
                    workspace.$new_data_div.dialog('open')}
                }
            }
        },
        "sources": {name: "Data Sources", callback: function(){
            workspace.data_sources.$div.dialog('open');
        }},
        "sep1": "--------------",
        "load_workspace": {name: "Load Workspace"},
        "save_workspace": {name: "Save Workspace", callback: function(){
            workspace.save_workspace();
        }},
        "save_ws_as": {name: "Save Workspace as", callback: function(){
            workspace.save_ws_as();
        }},
        "share_workspace": {name: "Share Workspace"},
        "logout": {name: "Logout", callback: function(){
            window.location = '/auth/logout/';
        }}
    }
    
    return items;
};

Toyz.Workspace.tile_contextMenu_items = function(workspace, custom_tiles){
    var tile_types = $.extend(true, {
        highcharts: {
            name: 'Highcharts',
            namespace: 'Toyz.API.Highcharts',
            url: '/static/web/static/api/highcharts.js'
        },
        viewer: {
            name:'Image viewer',
            namespace: 'Toyz.Viewer',
            url: '/static/web/static/viewer.js'
        }
    }, custom_tiles);
    
    for(var tile in tile_types){
        tile_types[tile].callback = function(key, options){
            workspace.tiles[options.$trigger.prop('id')].load_api(key, options.commands[key]);
        }
    };
    
    var items = {
        "tile_type": {
            name: "Tile Type",
            items: tile_types
        },
        "remove_tile": {name:"Remove Tile"},
        "tile_sep": "--------------"
    }
    items = $.extend(true, items, Toyz.Workspace.contextMenu_items(workspace));
    return items;
};

Toyz.Workspace.DataSource = function(workspace, id, params, $parent, radio_group, info){
    this.workspace = workspace;
    this.id = id;
    this.name = id;
    this.params = params;
    this.tiles = {};
    this.data = {};
    // Add an entry to a list of data sources
    if(!($parent===undefined)){
        this.$parent = $parent;
        this.$div = $('<div/>');
        this.$input = $('<input value="'+this.id+'"></input>')
            .change(function(){
                this.name = event.currentTarget.value;
            }.bind(this));
        if(radio_group===undefined){
            radio_group = 'data_src';
        };
        this.$div
            .append('<input type="radio" name="'+radio_group+'" value='+this.id+'></input>')
            .append(this.$input);
        $parent.append(this.$div);
    };
    // Update with any additionally added parameters
    if(!(info===undefined)){
        this.update(info);
    };
};
Toyz.Workspace.DataSource.prototype.update = function(info, info_val){
    // Allow user to either pass param_name, param_val to function or
    // dictionary with multiple parameters
    if(!(info_val===undefined)){
        info = {info:info_val};
    };
    // Make sure the data_type is set first, since other parameters may depend on it
    if(info.hasOwnProperty('data_type')){
        this.data_type = info.data_type;
    };
    for(var prop in info){
        if(prop=='data'){
            // Organize columns and data depending on the data_type received
            // If 'rows_no_heading' is received, an automatic list of column names is
            // created and the data_type is changed to 'rows'.
            if(this.data_type=='columns'){
                if(!(info.hasOwnProperty('columns'))){
                    this.columns = Object.keys(info.data);
                }
                this.data = info.data;
            }else if(this.data_type=='rows'){
                if(!(info.hasOwnProperty('columns'))){
                    this.columns = info.data[0];
                };
                this.data = info.data.slice(1,info.data.length);
            }else if(this.data_type=='rows_no_heading'){
                if(!(info.hasOwnProperty('columns'))){
                    this.columns = [];
                    for(var i=0;i<data[0].length;i++){
                        this.columns.push('col-'+i.toString());
                    };
                };
                this.data = info.data;
                this.data_type = 'rows';
            }else{
                var error = "You must initialize a data source with a data_type of "
                    + "'rows', 'columns' or 'rows_no_heading'";
                throw error;
            };
        }else if(prop=='name'){
            this.name = info.name;
            this.$input.val(this.name);
        }else{
            this[prop] = info[prop];
        }
    };
};
Toyz.Workspace.DataSource.prototype.remove = function(){
    // Remove jQuery objects
    for(var param in this){
        if(param[0]=='$'){
            this[param].remove();
        };
    };
    // Remove references to this data source
    for(var tile in this.tiles){
        tile.remove_source(this.name);
    };
};
Toyz.Workspace.DataSource.prototype.save = function(){
    var save_params = {
        params: this.params,
        tiles: this.tiles,
        name: this.name
    };
    return save_params;
};
Toyz.Workspace.DataSource.prototype.rx_info = function(from, info_type, info){
    // If any points are removed, remove them from the data source
    if(info_type=='remove datapoints'){
        for(var col in this.data){
            for(var i=info.points.length-1; i>=0; i--){
                this.data[col].splice(info.points[i], 1);
            }
        }
    };
    // Update tiles with the new information
    for(var tile_id in this.workspace.tiles){
        if(tile_id!=from){
            this.workspace.tiles[tile_id].contents.rx_info(this.id, info_type, info);
        }
    };
};

Toyz.Workspace.Tile = function(workspace, info){
    this.workspace = workspace;
    this.contents = {
        save: function(){},
        remove: function(){},
        rx_info: function(){}
    };
    
    this.update(info);
};
Toyz.Workspace.Tile.prototype.load_api = function(tile_api, api_settings){
    Toyz.Workspace.load_api_dependencies(
        tile_api, 
        api_settings.namespace,
        api_settings.url,
        this.update.bind(this,{
            contents: {
                api: api_settings.namespace
            }
        })
    );
};
Toyz.Workspace.Tile.prototype.update = function(info, info_val){
    // Allow user to either pass param_name, param_val to function or
    // dictionary with multiple parameters
    if(!(info_val===undefined)){
        var temp = {}
        temp[info] = info_val;
        info = temp;
    };
    for(var prop in info){
        if(prop == 'contents'){
            //console.log('contents', info.contents);
            var namespace = Toyz.Core.get_var(info.contents.api);
            this.contents = new namespace.Contents({
                tile: this,
                $tile_div: this.$inner_div,
                workspace: this.workspace
            });
            if(info.contents.hasOwnProperty('settings')){
                this.contents.set_tile(info.contents.settings);
            };
        }else{
            this[prop] = info[prop];
        }
    };
};

Toyz.Workspace.init_data_dialog = function(workspace){
    sources = {} || sources;
    var params = workspace.params.data_sources;
    
    if(!params.hasOwnProperty('options')){
        params.options={};
    };
    var data_dialog = $.extend(true, {
        $div: $('<div/>').prop('title', 'Data Sources'),
        src_index: 0,
        sources: {},
        editing:'',
        radio_group: 'data_src',
        workspace: workspace,
        load_src: function(callback, params, data_name){
            console.log('loading source', params, data_name);
            var data_id = data_dialog.editing;
            if(data_dialog.editing==''){
                data_id = 'data-'+(data_dialog.src_index++).toString();
            };
            if(data_name===undefined){
                data_name=data_id;
            };
            var src_params = $.extend(true, {}, params);
            
            // Load data from server
            var io_module = src_params['conditions'].io_module;
            var file_type = src_params['conditions'].file_type;
            delete src_params['conditions']
            workspace.websocket.send_task(
                {
                    module: 'toyz.web.tasks',
                    task: 'load_data_file',
                    parameters: {
                        io_module: io_module,
                        file_type: file_type,
                        file_options: src_params
                    }
                },
                data_dialog.add_src.bind(data_dialog, callback),
                {
                    id: data_id,
                    name: data_name,
                    params: params
                }
            );
            return data_id;
        },
        add_src: function(callback, result, params){
            console.log('added source to workspace', data_dialog.workspace)
            delete result.id;
            if(!(data_dialog.sources.hasOwnProperty(params.id))){
                data_dialog.sources[params.id] = new Toyz.Workspace.DataSource(
                    data_dialog.workspace,
                    params.id, 
                    params.params, 
                    data_dialog.$div, 
                    data_dialog.radio_group
                );
            };
            result.name = params.name;
            data_dialog.sources[params.id].update(result)
            workspace.$new_data_div.dialog('close');
            data_dialog.editing = '';
            if(!(callback===undefined)){
                callback();
            }
        },
        remove_src: function(source){
            if(source===undefined){
                source = $("input:radio[ name='"+data_dialog.radio_group+"' ]:checked").val()
            };
            if(!(source===undefined)){
                for(var param in data_dialog.sources[source]){
                    if(param[0]=='$' && param!='$parent'){
                        data_dialog.sources[source][param].remove();
                    }
                }
            }
            delete data_dialog.sources[source];
        },
        remove_all_sources: function(sources){
            if(sources===undefined){
                sources = data_dialog.sources;
            };
            for(var src in sources){
                data_dialog.remove_src(src);
            };
        },
        edit_src: function(){
            var source = $("input:radio[ name='"+data_dialog.radio_group+"' ]:checked").val();
            var src = data_dialog.sources[source];
            data_dialog.editing = source;
            if(!(source===undefined)){
                workspace.new_data_gui.setParams(
                    workspace.new_data_gui.params, src.params, false);
                workspace.$new_data_div.dialog('open');
            };
        },
        // Synchronously load sources
        update_sources: function(src_list, replace, callback){
            console.log('sources:', src_list);
            if(replace){
                data_dialog.remove_all_sources();
            };
            if(src_list.length==0){
                console.log('length = 0');
                callback();
            }else if(src_list.length==1){
                console.log('length = 1');
                data_dialog.load_src(callback, src_list[0].params, src_list[0].name);
            }else{
                console.log('length > 1');
                data_dialog.load_src(data_dialog.update_sources.bind(
                    null, 
                    src_list.slice(1, src_list.length),
                    false,
                    callback
                ));
            };
        },
    }, params.options);
    
    data_dialog.$div.dialog({
        resizable: true,
        draggable: true,
        autoOpen: false,
        modal: false,
        width: 'auto',
        height: '300',
        buttons: {
            New: function(){
                data_dialog.editing = '';
                workspace.$new_data_div.dialog('open');
            },
            Remove: function(){
                data_dialog.remove_src();
            },
            Edit: function(){
                data_dialog.edit_src();
            },
            Close: function(){
                data_dialog.$div.dialog('close');
            }
        }
    });
    
    return data_dialog;
};

Toyz.Workspace.init = function(params){
    var workspace = {
        name: undefined,
        $div: $('<div/>').addClass("workspace-div context-menu-one box menu-injected"),
        $parent: params.$parent,
        $new_data_div: $('<div/>')
            .prop('title', 'Open Data File')
            .addClass('open-dialog'),
        $ws_dropdown_div: $('<div/>').prop('title', 'Load Workspace'),
        tiles: {},
        tile_index: 0,
        params: $.extend(true,{},params),
        dependencies_onload: function(){
            console.log('all_dependencies_loaded');
            file_dialog = Toyz.Core.initFileDialog({
                websocket: workspace.websocket
            });
            workspace.file_dialog = file_dialog;
            
            workspace.websocket.send_task({
                module: 'toyz.web.tasks',
                task: 'get_io_info',
                parameters: {}
            });
            
            if(!workspace.params.hasOwnProperty('data_sources')){
                workspace.params.data_sources = {};
            };
            workspace.data_sources=Toyz.Workspace.init_data_dialog(workspace);
            workspace.$ws_dropdown_input = $('<select/>');
            
            workspace.$ws_dropdown_div.append(workspace.$ws_dropdown_input);
            workspace.$ws_dropdown_div.dialog({
                resizable: true,
                draggable: true,
                autoOpen: false,
                modal: false,
                width: 'auto',
                height: 'auto',
                buttons: {
                    Load: function(){
                        work_id = workspace.$ws_dropdown_input.val();
                        workspace.websocket.send_task(
                            {
                                module: 'toyz.web.tasks',
                                task: 'load_workspace',
                                parameters: {work_id: work_id}
                            },
                            workspace.update_workspace
                        );
                        workspace.$ws_dropdown_div.dialog('close');
                    },
                    Cancel: function(){
                        workspace.$ws_dropdown_div.dialog('close');
                    }
                }
            });
            
            // Initialize dialog to edit a tile's type and settings
            // workspace.tile_dialog = new Toyz.Workspace.TileDialog(workspace);
            
            // Create workspace context menu
            $.contextMenu({
                selector: '.context-menu-one', 
                callback: function(key, options) {
                    workspace[key](options);
                },
                items: Toyz.Workspace.contextMenu_items(workspace)
            });
            
            //create tile context menu
            $.contextMenu({
                selector: '.context-menu-tile',
                callback: function(key, options){
                    workspace[key](options);
                },
                items: Toyz.Workspace.tile_contextMenu_items(workspace)
            })
        },
        rx_msg: function(result){
            console.log('msg received:', result);
            if(result.id == 'io_info'){
                var param_div = $.extend(true,{},result.io_info);
                
                workspace.$new_data_div.dialog({
                    resizable: true,
                    draggable: true,
                    autoOpen: false,
                    modal: true,
                    width: 'auto',
                    height: '300',
                    buttons: {
                        Open: function(){
                            var params = workspace.new_data_gui.getParams(
                                workspace.new_data_gui.params
                            );
                            workspace.data_sources.load_src(undefined, params);
                        },
                        Cancel: function(){
                            workspace.$new_data_div.dialog('close');
                        }
                    }
                });
                
                workspace.new_data_gui = Toyz.Gui.initParamList(
                    param_div,
                    options = {
                        $parent: workspace.$new_data_div,
                    }
                );
                
                workspace.$new_data_div.dialog('widget').position({
                    my: "center",
                    at: "center",
                    of: window
                });
            }
        },
        save_workspace: function(params){
            if(workspace.name===undefined){
                workspace.save_ws_as();
            }else{
                var sources = {};
                for(var src in workspace.data_sources.sources){
                    sources[src] = workspace.data_sources.sources[src].save();
                };
                var ws_dict = {
                    workspaces: {},
                    overwrite: true
                };
                ws_dict.workspaces[workspace.name] = {
                    sources: sources,
                    tiles: workspace.save_tiles()
                }
                params = $.extend(true,ws_dict,params);
                workspace.websocket.send_task(
                    {
                        module: 'toyz.web.tasks',
                        task: 'save_workspace',
                        parameters: params
                    },
                    function(result){
                        if(result.id=='verify'){
                            if(confirm("Workspace name already exists, overwrite?")){
                                workspace.save_workspace();
                            }
                        }
                    }
                );
            }
        },
        save_ws_as: function(){
            workspace.name = prompt("New workspace name");
            if(workspace.name != null){
                workspace.save_workspace({overwrite:false});
            }
        },
        load_workspace: function(){
            workspace.websocket.send_task(
                {
                    module: 'toyz.web.tasks',
                    task: 'load_user_info',
                    parameters:{
                        user_id: workspace.websocket.user_id,
                        user_attr: ['workspaces'],
                    }
                },
                function(result){
                    workspace.$ws_dropdown_input.empty();
                    for(var key in result.workspaces){
                        var opt = $('<option/>')
                            .val(key)
                            .text(key);
                        workspace.$ws_dropdown_input.append(opt);
                    }
                    workspace.$ws_dropdown_div.dialog('open');
                }
            )
        },
        // First load all of the data sources, then update the tiles once all of the
        // data has been loaded from the server
        update_workspace: function(result){
            console.log('load result', result);
            var sources = Object.keys(result.settings.sources);
            var src_list = [];
            for(var i=0; i<sources.length;i++){
                src_list.push(result.settings.sources[sources[i]]);
            };
            workspace.name = result.work_id;
            workspace.data_sources.update_sources(
                src_list, 
                replace=true,
                callback = function(tiles){
                    this.load_tiles(tiles);
                }.bind(workspace, result.settings.tiles)
            );
            console.log('done updating');
        },
        share_workspace: function(){
        },
        new_tile: function(key, options, my_idx){
            if(my_idx===undefined){
                my_idx = workspace.tile_index++;
            }else if(workspace.tile_index<=my_idx){
                workspace.tile_index = my_idx+1;
            };
            my_idx = my_idx.toString();
            var inner_id = 'tile-'+my_idx;
            var my_id = 'tile-div'+my_idx;
            var $inner_div = $('<div/>')
                .prop('id',inner_id)
                .addClass('ws-inner-div context-menu-tile box menu-injected');
            
            var $div = $('<div/>')
                .prop('id',my_id)
                .addClass('ws-tile context-menu-tile box menu-injected')
                .draggable({
                    stack: '#'+my_id,
                    cancel: '#'+inner_id,
                    grid: [5,5],
                    containment: 'parent'
                })
                .resizable({
                    autoHide: true,
                    handles: "ne,se,nw,sw",
                    grid: [5,5]
                })
                .css({
                    position: 'absolute',
                    top: Math.floor(window.innerHeight/2),
                    left: Math.floor(window.innerWidth/2),
                });
            $div.append($inner_div);
            workspace.$div.append($div);
            workspace.tiles[inner_id] = new Toyz.Workspace.Tile(workspace, {
                id: inner_id,
                $div: $div,
                $inner_div: $inner_div,
            });
            return workspace.tiles[inner_id];
        },
        remove_tile: function(options){
            var my_id = options.$trigger.prop('id');
            workspace.tiles[my_id].$div.remove();
            
            // tile.remove() is a function that may differ depending on the
            // type of object displayed in the tile
            workspace.tiles[my_id].contents.remove();
            delete workspace.tiles[my_id];
        },
        save_tiles: function(){
            var tiles = {};
            for(var tile_id in workspace.tiles){
                var tile = workspace.tiles[tile_id];
                tiles[tile_id] = {
                    tile_id: tile_id,
                    top: tile.$div.offset().top,
                    left: tile.$div.offset().left,
                    width: tile.$div.width(),
                    height: tile.$div.height()
                };
                tiles[tile_id].contents = tile.contents.save();
            };
            return tiles;
        },
        load_tiles: function(tiles){
            console.log('load tiles', tiles);
            var api_list = [];
            for(var tile_id in tiles){
                if(api_list.indexOf(tiles[tile_id].contents.type)==-1){
                    api_list.push(tiles[tile_id].contents.type);
                };
            };
            workspace.load_tile_apis(api_list, tiles);
        },
        // Load Tile API's synchronously, then update all of the tiles
        load_tile_apis: function(api_list, tiles){
            var callback;
            if(api_list.length==1){
                callback = workspace.update_all_tiles.bind(null, tiles);
            }else{
                callback = workspace.load_tile_apis.bind(
                    null,
                    api_list.slice(1,api_list.length),
                    tiles
                );
            };
            var all_apis = Toyz.Workspace.tile_contextMenu_items(workspace).tile_type.items;
            console.log('all apis', all_apis);
            console.log('api', api_list[0]);
            if(!all_apis.hasOwnProperty(api_list[0])){
                alert("API not found in toyz")
                throw "API not found in toyz"
            };
            Toyz.Workspace.load_api_dependencies(
                tile_api=api_list[0],
                namespace=all_apis[api_list[0]].namespace,
                url=all_apis[api_list[0]].url,
                callback
            )
        },
        update_all_tiles: function(tiles){
            var new_tiles = {};
            for(var tile_id in tiles){
                new_tiles[tile_id] = workspace.new_tile(null, null, tile_id.split('-')[1]);
                new_tiles[tile_id].$div.css({
                    top: tiles[tile_id].top,
                    left: tiles[tile_id].left,
                    width: tiles[tile_id].width,
                    height: tiles[tile_id].height
                });
                var all_apis = Toyz.Workspace.tile_contextMenu_items(workspace).tile_type.items;
                new_tiles[tile_id].update({
                    contents: {
                        workspace: workspace,
                        api: all_apis[tiles[tile_id].contents.type].namespace,
                        settings: tiles[tile_id].contents.settings
                    }
                });
            };
            workspace.tiles = new_tiles;
        }
    };
    
    workspace.websocket = Toyz.Core.jobsocketInit({
        receiveAction: workspace.rx_msg,
        //logger:new Toyz.Core.Logger(document.getElementById("logger")),
    });
    
    Toyz.Core.load_dependencies(
        dependencies={
            core: true
        }, 
        callback=workspace.dependencies_onload
    );
    
    params.$parent.append(workspace.$div);
    
    return workspace;
};

console.log('workspace.js loaded');