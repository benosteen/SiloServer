from recordsilo import Silo

import web

import sys

import mimetypes
mimetypes.init()

from web.contrib.template import render_mako

from urllib import urlencode, unquote, quote

from datetime import datetime

from pprint import pprint

urls = (
        '/', 'usage',
        '/(.*)', 'api',
        )

app = web.application(urls, globals(), autoreload=True)

data_dir = "../economics_repo/"

s = Silo(data_dir)

# input_encoding and output_encoding is important for unicode
# template file. Reference:
# http://www.makotemplates.org/docs/documentation.html#unicode
render = render_mako(
        directories=['templates'],
        input_encoding='utf-8',
        output_encoding='utf-8',
        )

class usage:
    def GET(self):
        items = s.list_items()
        return render.usage(items = items)
        
    def POST(self):
        x = web.input()
        if x.has_key("id"):
            if not s.exists(x['id']):
                item = s.get_item(x['id'])
                raise web.created()
            else:
                raise web.ok()

class api:
    def GET(self, path):
        path = unquote(path)
        tokens = [x for x in path.split("/") if x]
        if len(tokens) == 1:
            web.header('Content-type','text/html; charset=utf-8', unique=True)
            if s.exists(tokens[0]):
                item = s.get_item(tokens[0])
                web.header('Last-Modified',item.date)
                yield render.object(item=item)
            else:
                raise web.notfound()
        elif len(tokens) == 2:
            web.header('Content-type','text/html; charset=utf-8', unique=True)
            if s.exists(tokens[0]):
                item = s.get_item(tokens[0])
                if tokens[1] in item.versions:
                    item.set_version_cursor(tokens[1])
                    web.header('Last-Modified',item.date)
                    yield render.version(item=item, version=tokens[1])
                else:
                    raise web.notfound()
            else:
                raise web.notfound()
        elif len(tokens) > 2:
            if s.exists(tokens[0]):
                item = s.get_item(tokens[0])
                if tokens[1] in item.versions:
                    item.set_version_cursor(tokens[1])
                    web.header('Last-Modified',item.date)
                    filepath = "/".join(tokens[2:])
                    if item.isdir(filepath):
                        yield render.subpath(item=item, version = tokens[1], subpath=filepath)
                    elif item.isfile(filepath):
                        (t,e) = mimetypes.guess_type(filepath)
                        if t:
                            web.header('Content-type',t, unique=True)
                        if e:
                            web.header('Content-Encoding',e, unique=True)
                        with item.get_stream(filepath) as response_obj:
                            chunk = response_obj.read(1024*8*8)  #64k chunk
                            while chunk:
                                yield chunk
                                chunk = response_obj.read(1024*8*8)  #64k chunk
                    else:
                        raise web.notfound()
                else:
                    raise web.notfound()
            else:
                raise web.notfound()

    def POST(self, path):
        path = unquote(path)
        tokens = [x for x in path.split("/") if x]
        if len(tokens) == 1:
            x = web.input()
            if x.has_key("version"):
                item = s.get_item(tokens[0])
                if x['version'] not in item.versions:
                    if x.has_key("old_version"):
                        item.clone_version(x['old_version'], x['version'])
                        raise web.created()
                    else:
                        item.create_new_version(x['version'], date=datetime.now().isoformat())
                        raise web.created()
                else:
                    raise web.ok()
                
        elif len(tokens) == 2:
            if s.exists(tokens[0]):
                item = s.get_item(tokens[0])
                if tokens[1] not in item.versions:
                    item.create_new_version(tokens[1], date=datetime.now().isoformat())
                    raise web.created()
                else:
                    x = web.input(part={})
                    if x.has_key("part"):
                        item.set_version_cursor(tokens[1])
                        path = x['part'].filename
                        if x.has_key("path") and x['path']:
                            path = x['path']
                        new = True
                        if path in item.files:
                            new = False
                        item.put_stream(path, x['part'].file)
                        x['part'].file.close()
                        if new:
                            raise web.created()
                        else:
                            raise web.ok()
                    else:
                        raise web.ok()
            else:
                raise web.notfound()
        elif len(tokens) > 2:
            if s.exists(tokens[0]):
                item = s.get_item(tokens[0])
                if tokens[1] not in item.versions:
                    item.create_new_version(tokens[1], date=datetime.now().isoformat())
                x = web.input(part={})
                item.set_version_cursor(tokens[1])
                #mimetype = "application/octet-stream"
                #if params['part'].headers.has_key('content-type'):
                #    mimetype = params['part'].headers['content-type']
                path = x['part'].filename
                if x.has_key("path") and x['path']:
                    path = x['path']
                new = True
                if path in item.files:
                    new = False
                item.put_stream(path, x['part'].file)
                x['part'].file.close()
                if new:
                    raise web.created()
                else:
                    raise web.ok()
            else:
                raise web.notfound()

    def DELETE(self, path):
        path = unquote(path)
        tokens = [x for x in path.split("/") if x]
        if len(tokens) == 1:
            if s.exists(tokens[0]):
                s.del_item(tokens[0])
                raise web.ok()
            else:
                raise web.notfound()
        elif len(tokens) == 2:
            if s.exists(tokens[0]):
                item = s.get_item(tokens[0])
                if tokens[1] not in item.versions:
                    raise web.notfound()
                else:
                    item.del_version(tokens[1])
                    return "{'ok':'true'}"
            else:
                raise web.notfound()
        elif len(tokens) > 2:
            if s.exists(tokens[0]):
                item = s.get_item(tokens[0])
                if tokens[1] not in item.versions:
                    raise web.notfound()
                else:
                    item.set_version_cursor(tokens[1])
                    filepath = "/".join(tokens[2:])
                    if item.isfile(filepath):
                        item.del_stream(filepath)
                        return "{'ok':'true'}"
                    elif item.isdir(filepath):
                        try:
                            item.del_stream(filepath)
                            return "{'ok':'true'}"
                        except OSError:
                            raise web.forbidden("The subpath directory is not empty")
                    else:
                        raise web.notfound()
            else:
                raise web.notfound()

if __name__ == "__main__":
    app.run()
