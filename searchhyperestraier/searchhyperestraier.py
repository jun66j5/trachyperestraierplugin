# -*- coding: utf-8 -*-

from __future__ import with_statement

from datetime import datetime
from pkg_resources import parse_version
from subprocess import PIPE, Popen
from xml.dom import minidom
import fnmatch
import os.path
import re
import shlex
import shutil
import tempfile
import time
import urllib

from trac import __version__ as VERSION
from trac.admin.api import IAdminCommandProvider
from trac.attachment import Attachment
from trac.config import BoolOption, ListOption, Option, PathOption
from trac.core import Component, TracError, implements
from trac.db.api import get_column_names
from trac.env import Environment
from trac.mimeview.api import Mimeview, get_mimetype
from trac.resource import ResourceNotFound, get_resource_url, \
                          get_resource_shortname
from trac.search.api import ISearchSource
from trac.util.compat import close_fds
from trac.util.datefmt import format_datetime, from_utimestamp, to_datetime, \
                              utc
from trac.util.text import exception_to_unicode, printerr, unicode_unquote
from trac.versioncontrol.api import RepositoryManager
from trac.web.chrome import add_warning
from trac.web.href import Href


_has_files_dir = parse_version(VERSION) >= parse_version('1.0')

if os.name == 'nt':
    def _get_fs_encoding():
        import ctypes
        MAX_DEFAULTCHAR = 2
        MAX_LEADBYTES = 12
        MAX_PATH = 260
        CP_ACP = 0
        GetCPInfoExW = ctypes.windll.kernel32.GetCPInfoExW
        class CPInfoExW(ctypes.Structure):
            _fields_ = (
                ('MaxCharSize', ctypes.c_uint),
                ('DefaultChar', ctypes.c_byte * MAX_DEFAULTCHAR),
                ('LeadByte', ctypes.c_byte * MAX_LEADBYTES),
                ('UnicodeDefaultChar', ctypes.c_wchar),
                ('CodePage', ctypes.c_uint),
                ('CodePageName', ctypes.c_wchar * MAX_PATH),
            )
        buf = CPInfoExW()
        if GetCPInfoExW(CP_ACP, 0, ctypes.byref(buf)) != 0:
            return 'cp%d' % buf.CodePage
        else:
            return 'mbcs'
    _fs_encoding = _get_fs_encoding()
    del _get_fs_encoding
else:
    _fs_encoding = 'utf-8'


class SearchHyperEstraierModule(Component):

    implements(ISearchSource)

    estcmd_path = Option('searchhyperestraier', 'estcmd_path', 'estcmd')
    estcmd_arg = Option('searchhyperestraier', 'estcmd_arg',
                        'search -vx -sf -ic %s' % _fs_encoding)
    browse_trac = BoolOption('searchhyperestraier', 'browse_trac', 'enabled')
    att_index_path = PathOption(
        'searchhyperestraier', 'att_index_path',
        '../files/attachments-index' if _has_files_dir else
        '../attachments-index')
    doc_index_path = PathOption('searchhyperestraier', 'doc_index_path', '')
    doc_replace_left = Option('searchhyperestraier', 'doc_replace_left', '')
    doc_url_left = Option('searchhyperestraier', 'doc_url_left', 'doc')
    filters = ListOption('searchhyperestraier', 'filters', '',
        doc=u"""\
ファイル名に合わせてフィルタを `*.ext=filter` 形式で指定します。

 * 複数のファイル名に対して同時にフィルタを指定したいときには `:` を使えます。
 * フィルタの実行時にはファイル名が引数に渡されます。
 * フィルタの出力形式に合わせて、フィルタの直前に `T@` (テキスト) `H@` (HTML) `M@` (MIME) を指定します。
 * フィルタの出力は UTF-8 エンコーディングになるようにします。

設定例1:
{{{#!ini
[searchhyperestraier]
filters = *.xls:*.doc:*.ppt=H@/usr/share/hyperestraier/filter/estfxmsotohtml,
          *.pdf=H@/usr/share/hyperestraier/filter/estfxpdftohtml,
          *.txt=T@/usr/share/hyperestraier/filter/estfxasis
}}}

設定例2:
{{{#!ini
[searchhyperestraier]
filters = *.xls:*.xlsx:*.doc:*.docx:*.ppt:*.pptx=T@C:\\apps\\xdoc2txt.exe -i -p -8,
          *=T@C:\\apps\\xdoc2txt.exe -i -8
}}}
""")

    # ISearchProvider methods

    def get_search_filters(self, req):
        if req.perm.has_permission('BROWSER_VIEW'):
            yield ('repositoryhyperest', u'he:リポジトリ', 0)

    def get_search_results(self, req, terms, filters):
        if not 'repositoryhyperest' in filters:
            return

        browse_trac = self.browse_trac

        #for multi repos
        for option in self.config['searchhyperestraier']:
            #リポジトリのパス
            if not option.endswith('.index_path'):
                continue
            mrepstr = option[:-len('.index_path')] #'.index_path'の前の文字列がreponame
            if RepositoryManager(self.env).get_repository(mrepstr) is None: #mrepstrのrepositoryがない
                continue
            #インデックスのパス
            index_path = self.config.get('searchhyperestraier', mrepstr+'.index_path')
            if not index_path:  #mrepstr+'.index_path'がない
                continue
            #検索結果のパスの頭で削る文字列
            replace_left = self.config.get('searchhyperestraier', mrepstr+'.replace_left')
            if not replace_left:  #mrepstr+'.replace_left'がない
                continue
            #URLを生成する際に頭につける文字列
            #browse_trac=enabledの場合は/がリポジトリのルートになるように
            url_left = self.config.get('searchhyperestraier', mrepstr+'.url_left')
            if not url_left:  #mrepstr+'.url_left'がない
                continue
            if mrepstr != '': #defaultでない
                url_left = '/' + mrepstr + url_left

            dom = self._search_index(req, index_path, terms)
            if not dom:
                continue
            root = dom.documentElement
            #estresult_node = root.getElementsByTagName("document")[0]
            element_array = root.getElementsByTagName("document")
            for element in element_array:
                url = ""
                title = ""
                date = 0
                detail = ""
                author = u"不明"

                #detailを生成
                elem_array =  element.getElementsByTagName("snippet")
                detail = _get_inner_text(elem_array)

                #その他の属性を生成
                attrelem_array = element.getElementsByTagName("attribute")
                for attrelem in attrelem_array:
                    attr_name = attrelem.getAttribute("name")
                    attr_value = unicode(attrelem.getAttribute("value"))
                    #URLとタイトルを生成
                    #if attr_name == "_lreal": #"_lreal"ではファイル名に'  'などが入っている場合対応できない
                    #    attr_value=attr_value[len(replace_left):].replace("\\","/")
                    #    if browse_trac == "enabled":
                    #        url = self.env.href.browser(url_left + attr_value)
                    #        title = "source:"+ url_left + attr_value
                    #    else:
                    #        url = url_left + attr_value
                    #        title = url_left + attr_value
                    if attr_name == "_lpath": #s-jisをquoteしたもの("file:///C|/TracLight/…"の形式)
                        attr_value = _decode_urlencoded_value(attr_value,
                                                              _fs_encoding)
                        attr_value = attr_value[(len('file:///')+len(replace_left)):]
                        if browse_trac:
                            url = self.env.href.browser(url_left + attr_value)
                            title = "source:" + \
                                    _decode_urlencoded_value(url, 'utf-8')
                        else:
                            url = url_left + attr_value
                            title = _decode_urlencoded_value(url, 'utf-8')
                    #更新日時を生成
                    elif attr_name =="@mdate":
                        date = time.strptime(attr_value,"%Y-%m-%dT%H:%M:%SZ")
                        self.log.debug('date:%r', attr_value)
                        date = to_datetime(datetime(date[0],date[1],date[2],date[3],date[4],date[5],0,utc)) # for Trac0.11
                yield(url,title,date,author,detail)
        return

    def _search_index(self, req, index_path, terms):
        args = [self.estcmd_path]
        args.extend(self.estcmd_arg.split())
        args.append(index_path)
        args.extend(terms)
        encoding = 'mbcs' if os.name == 'nt' else 'utf-8'
        args = [arg.encode(encoding, 'replace')
                if isinstance(arg, unicode) else arg
                for arg in args]
        proc = Popen(args, close_fds=close_fds, stdin=PIPE, stdout=PIPE,
                     stderr=PIPE)
        try:
            stdout, stderr = proc.communicate(input='')
        finally:
            for f in (proc.stdin, proc.stdout, proc.stderr):
                if f:
                    f.close()
        rc = proc.returncode
        if rc != 0:
            add_warning(req, 'Unable to search index: estcmd exits with %d' %
                             rc)
            self.log.error('Unable to search index: estcmd exits with %d '
                           '(stdout=%r, stderr=%r)', rc, stdout, stderr)
            return None
        if not stdout:
            return None
        try:
            return minidom.parseString(stdout)
        except Exception, e:
            add_warning(req, 'Unable to search index: %s' %
                             exception_to_unicode(e))
            self.log.error('Unable to search index: %r%s', stdout,
                           exception_to_unicode(e, traceback=True))
            return None

    def _get_filters(self):
        rv = []
        for filter_ in self.filters:
            patterns, cmd = [v.strip() for v in filter_.split('=', 1)]
            patterns = re.compile(r'(?:%s)' %
                                  '|'.join(fnmatch.translate(p.strip())
                                           for p in patterns.split(':')))
            if cmd.startswith(('T@', 'H@', 'M@')):
                type_ = cmd[0:1]
                cmd = cmd[2:]
            else:
                type_ = None
            cmd = _shlex_split(cmd)
            rv.append((patterns, type_, cmd))
        return rv

    def _get_mimetype(self, filename):
        mimeview = Mimeview(self.env)
        return get_mimetype(filename, None, mimeview.mime_map,
                            mimeview.mime_map_patterns) or \
               'application/octet-stream'

    def _verify_estcmd_path(self):
        args = (self.estcmd_path, '--version')
        try:
            with open(os.devnull, 'r') as stdin:
                with open(os.devnull, 'a+') as stdout:
                    with open(os.devnull, 'a+', 0) as stderr:
                        proc = Popen(args, close_fds=close_fds, stdin=stdin,
                                     stdout=stdout, stderr=stderr)
                        rv = proc.wait()
        except EnvironmentError, e:
            raise TracError('Unable to execute estcmd: %r (%s)' %
                            (args, exception_to_unicode(e)))
        else:
            if rv != 0:
                raise TracError('estcmd exits with %d: %r' % (rv, args))


class SearchChangesetHyperEstraierModule(Component):

    implements(ISearchSource)

    # ISearchProvider methods

    def get_search_filters(self, req):
        if req.perm.has_permission('CHANGESET_VIEW'):
            yield ('changesethyperest', u'he:チェンジセット', 0)

    def get_search_results(self, req, terms, filters):
        if not 'changesethyperest' in filters:
            return

        mod = SearchHyperEstraierModule(self.env)

        #for multi repos
        for option in self.config['searchhyperestraier']:
            #リポジトリのパス
            if not option.endswith('.cs_index_path'):
                continue
            mrepstr = option[:-len('.cs_index_path')] #'.cs_index_path'の前の文字列がreponame
            if RepositoryManager(self.env).get_repository(mrepstr) is None: #mrepstrのrepositoryがない
                continue
            repoinfo = RepositoryManager(self.env).get_all_repositories().get(mrepstr, {})
            #self.log.debug('type:%r', repoinfo.get('type'))
            if repoinfo.get('type') != 'direct-svnfs':#'direct-svnfs'のリポジトリでない
                continue
            #インデックスのパス
            cs_index_path = self.config.get('searchhyperestraier', mrepstr+'.cs_index_path')
            if not cs_index_path:  #mrepstr+'.cs_index_path'がない
                continue
            if mrepstr != '': #defaultでない
                mrepstr = '/' + mrepstr

            dom = mod._search_index(req, cs_index_path, terms)
            if not dom:
                continue
            root = dom.documentElement
            #estresult_node = root.getElementsByTagName("document")[0]
            element_array = root.getElementsByTagName("document")
            for element in element_array:
                url = ""
                title = ""
                date = 0
                detail = ""
                author = u"不明"

                #detailを生成
                elem_array =  element.getElementsByTagName("snippet")
                detail = _get_inner_text(elem_array)

                #その他の属性を生成
                attrelem_array = element.getElementsByTagName("attribute")
                for attrelem in attrelem_array:
                    attr_name = attrelem.getAttribute("name")
                    attr_value = unicode(attrelem.getAttribute("value"))
                    #URLとタイトルを生成
                    if attr_name == "_lreal":
                        attr_value=attr_value.replace(".txt","")
                        end = len(attr_value)
                        for m in range(1,end):
                            if not attr_value[(end-m):].isdigit():
                                break
                        attr_value = attr_value[(end-m+1):] + mrepstr #数字の文字列 + mrepstr
                        url = self.env.href('/changeset/' + attr_value )
                        title = "changeset:" + attr_value
                    #更新日時を生成
                    elif attr_name =="@mdate":
                        date = time.strptime(attr_value,"%Y-%m-%dT%H:%M:%SZ")
                        self.log.debug('date:%r', attr_value)
                        date = to_datetime(datetime(date[0],date[1],date[2],date[3],date[4],date[5],0,utc)) # for Trac0.11
                yield(url,title,date,author,detail)
        return


class SearchAttachmentHyperEstraierModule(Component):

    implements(IAdminCommandProvider, ISearchSource)

    # IAdminCommandProvider methods

    def get_admin_commands(self):
        yield ('searchhyperestraier gather attachments', '',
               'Gather attachments', None, self._do_gather)

    # ISearchProvider methods

    def get_search_filters(self, req):
        mod = SearchHyperEstraierModule(self.env)
        att_index_path = mod.att_index_path
        if att_index_path and os.path.exists(att_index_path):
            yield ('attachmenthyperest', u'he:添付ファイル', 0)

    def get_search_results(self, req, terms, filters):
        if not 'attachmenthyperest' in filters:
            return

        mod = SearchHyperEstraierModule(self.env)
        dom = mod._search_index(req, mod.att_index_path, terms)
        if not dom:
            return

        for node in dom.documentElement.getElementsByTagName('document'):
            detail = _get_inner_text(node.getElementsByTagName('snippet'))
            uri = node.getAttribute('uri')
            if isinstance(uri, unicode):
                uri = uri.encode('utf-8')
            uri = unicode_unquote(uri)
            if uri.startswith('attachment:/'):
                segments = uri[12:].split('/')
                type_ = segments[0]
                id_ = '/'.join(segments[1:-1])
                filename = segments[-1]
                try:
                    att = Attachment(self.env, type_, id_, filename)
                except ResourceNotFound:
                    continue
                url = get_resource_url(self.env, att.resource, req.href)
                title = get_resource_shortname(self.env, att.resource)
                yield url, title, att.date, att.author, detail
        return

    # Internal methods

    @property
    def _estcmd_path(self):
        return SearchHyperEstraierModule(self.env).estcmd_path

    if hasattr(Environment, 'database_version'):
        @property
        def _db_version(self):
            return self.env.database_version
    else:
        @property
        def _db_version(self):
            return self.env.get_version()

    def _popen(self, **kwargs):
        kwargs.setdefault('close_fds', close_fds)
        try:
            proc = Popen(**kwargs)
        except EnvironmentError as e:
            self.log.warning('Unable to execute: %r%s', kwargs.get('args'),
                             exception_to_unicode(e, traceback=True))
            raise TracError('Unable to execute: %s' % repr(kwargs.get('args')))
        return proc.wait()

    def _do_gather(self):
        mod = SearchHyperEstraierModule(self.env)
        mod._verify_estcmd_path()

        if self._db_version >= 29:  # Trac 1.0 or later
            def attachment_path(row):
                return Attachment._get_path(self.env.path, row['type'],
                                            row['id'], row['filename'])
        else:
            def attachment_path(row):
                att = Attachment(self.env)
                return att._get_path(row['type'], row['id'], row['filename'])

        filters = mod._get_filters()
        if not filters:
            raise TracError('filters option is empty')
        dir_ = tempfile.mkdtemp()
        try:
            with self.env.db_query as db:
                cursor = db.cursor()
                cursor.execute("SELECT * FROM attachment")
                columns = get_column_names(cursor)
                skipped = 0
                for idx, row in enumerate(cursor):
                    row = dict(zip(columns, row))
                    for patterns, filter_type, cmd in filters:
                        if not patterns.match(row['filename']):
                            continue
                        src_file = attachment_path(row)
                        dst_file = os.path.join(dir_, '%08d.est' % idx)
                        self._create_draft(dst_file, src_file, filter_type,
                                           cmd, row)
                        break
                    else:
                        self.log.warning("Skipped '%s' in %s:%s",
                                         row['filename'], row['type'],
                                         row['id'])
                        skipped += 1
                if skipped > 0:
                    self.log.warning('Skipped %d attachments', skipped)
                    printerr('Skipped %d attachments' % skipped)
                self._popen(args=(self._estcmd_path, 'gather',
                                  mod.att_index_path, dir_))
        finally:
            shutil.rmtree(dir_)

    def _create_draft(self, dst_file, src_file, filter_type, cmd, row):
        tmp1_file = dst_file + '.tmp1'
        tmp2_file = dst_file + '.tmp2'
        try:
            with open(tmp2_file, 'wb+') as tmp2:
                with open(tmp1_file, 'wb+') as tmp1:
                    self._popen(args=(cmd + (src_file,)), stdout=tmp1)
                    tmp1.seek(0, 0)
                    args = [self._estcmd_path, 'draft']
                    if filter_type:
                        args.append({'T': '-ft', 'H': '-fh', 'M': '-fm'}
                                    .get(filter_type))
                    self._popen(args=args, stdin=tmp1, stdout=tmp2)
                with open(dst_file, 'wb') as dst:
                    tmp2.seek(0, 0)
                    headers = {}
                    while True:
                        line = tmp2.readline()
                        line = line.rstrip('\r\n')
                        if not line:
                            break
                        key, val = line.split('=', 1)
                        headers[key] = val
                    filename = row['filename']
                    mdate = from_utimestamp(row['time'])
                    headers['@uri'] = Href('attachment:') \
                                      (row['type'], row['id'], filename)
                    headers['@mdate'] = format_datetime(mdate, 'iso8601', utc)
                    headers['@size'] = str(row['size'])
                    headers['@type'] = SearchHyperEstraierModule(self.env) \
                                       ._get_mimetype(filename)
                    for key, val in headers.iteritems():
                        if isinstance(val, unicode):
                            val = val.encode('utf-8')
                        dst.write('%s=%s\n' % (key, val))
                    dst.write('\n')
                    while True:
                        chunk = tmp2.read(4096)
                        if not chunk:
                            break
                        dst.write(chunk)
        finally:
            for path in (tmp1_file, tmp2_file):
                if os.path.exists(path):
                    os.remove(path)


class SearchDocumentHyperEstraierModule(Component):

    implements(ISearchSource)

    # ISearchProvider methods

    def get_search_filters(self, req):
        mod = SearchHyperEstraierModule(self.env)
        if mod.doc_index_path and mod.doc_replace_left and \
                mod.doc_url_left and os.path.exists(mod.doc_index_path):
            yield ('documenthyperest', u'he:ドキュメント', 0)

    def get_search_results(self, req, terms, filters):
        if not 'documenthyperest' in filters:
            return

        mod = SearchHyperEstraierModule(self.env)
        doc_replace_left = mod.doc_replace_left
        doc_url_left = mod.doc_url_left
        dom = mod._search_index(req, mod.doc_index_path, terms)
        if not dom:
            return

        root = dom.documentElement
        #estresult_node = root.getElementsByTagName("document")[0]
        element_array = root.getElementsByTagName("document")
        for element in element_array:
            url = ""
            title = ""
            date = 0
            detail = ""
            author = u"不明"

            #detailを生成
            elem_array =  element.getElementsByTagName("snippet")
            detail = _get_inner_text(elem_array)

            #その他の属性を生成
            attrelem_array = element.getElementsByTagName("attribute")
            for attrelem in attrelem_array:
                attr_name = attrelem.getAttribute("name")
                attr_value = unicode(attrelem.getAttribute("value"))
                #URLとタイトルを生成
                #if attr_name == "_lreal": #"_lreal"ではファイル名に'  'などが入っている場合対応できない
                #    attr_value=attr_value[len(doc_replace_left):].replace("\\","/")
                #    title = doc_url_left + attr_value
                #    url = urllib.quote(title.encode('utf-8'))
                #    title = '/' + title
                if attr_name == "_lpath": #s-jisをquoteしたもの("file:///C|/TracLight/…"の形式)
                    attr_value = _decode_urlencoded_value(attr_value,
                                                          _fs_encoding)
                    attr_value = attr_value[(len('file:///')+len(doc_replace_left)):]
                    #url = doc_url_left + attr_value
                    #title = '/' + urllib.unquote(url)
                    title = '/' + doc_url_left + attr_value
                    url = urllib.quote((doc_url_left + attr_value).encode('utf-8'))
                #更新日時を生成
                elif attr_name =="@mdate":
                    date = time.strptime(attr_value,"%Y-%m-%dT%H:%M:%SZ")
                    self.log.debug('date:%r', attr_value)
                    date = to_datetime(datetime(date[0],date[1],date[2],date[3],date[4],date[5],0,utc)) # for Trac0.11
            yield(url,title,date,author,detail)
        return


def _get_inner_text(node_array):
    def to_text(node):
        if node.nodeType == node.TEXT_NODE:
            text = node.data
            if not isinstance(text, unicode):
                text = unicode(text, 'utf-8')
            return text
        else:
            return _get_inner_text(node.childNodes)
    return u''.join(to_text(node) for node in node_array)


def _shlex_split(value):
    if isinstance(value, unicode):
        value = value.encode('utf-8')
    l = shlex.shlex(value, posix=True)
    l.escape = ''
    l.whitespace_split = True
    return tuple(l)


def _decode_urlencoded_value(value, encoding):
    value = urllib.unquote(value)
    value = value.encode('raw_unicode_escape')
    value = value.decode(encoding)
    return value
