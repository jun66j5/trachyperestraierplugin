# -*- coding: utf-8 -*-

from datetime import datetime
from xml.dom.minidom import parseString
import os.path
import time
import urllib

from trac.core import Component, implements
from trac.config import BoolOption, Option
from trac.search.api import ISearchSource
from trac.util import NaivePopen
from trac.util.datefmt import to_datetime, utc
from trac.util.text import to_unicode
from trac.versioncontrol.api import RepositoryManager


class SearchHyperEstraierModule(Component):

    implements(ISearchSource)

    estcmd_path = Option('searchhyperestraier', 'estcmd_path', 'estcmd')
    estcmd_arg = Option('searchhyperestraier', 'estcmd_arg',
                        'search -vx -sf -ic Shift_JIS')
    estcmd_encode = Option('searchhyperestraier', 'estcmd_encode', 'mbcs')
    browse_trac = BoolOption('searchhyperestraier', 'browse_trac', 'enabled')
    att_index_path = Option('searchhyperestraier', 'att_index_path', '')
    doc_index_path = Option('searchhyperestraier', 'doc_index_path', '')
    doc_replace_left = Option('searchhyperestraier', 'doc_replace_left', '')
    doc_url_left = Option('searchhyperestraier', 'doc_url_left', 'doc')

    # ISearchProvider methods
    def get_search_filters(self, req):
        if req.perm.has_permission('BROWSER_VIEW'):
            yield ('repositoryhyperest', u'he:リポジトリ', 0)

    def get_search_results(self, req, terms, filters):
        if not 'repositoryhyperest' in filters:
            return

        estcmd_path = self.estcmd_path
        estcmd_arg = self.estcmd_arg
        estcmd_encode = self.estcmd_encode
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

            #cmdline = "%s %s %s %s" % (estcmd_path,estcmd_arg,index_path,unicode(query,'utf-8').encode('CP932'))
            qline = ' '.join(terms)
            cmdline = "%s %s %s %s" % (estcmd_path,estcmd_arg,index_path,qline)
            self.log.debug('SearchHyperEstraier:%r', cmdline)
            cmdline = unicode(cmdline).encode(estcmd_encode)
            np = NaivePopen(cmdline)
            #self.log.debug('Result:%s', np.out)
            if np.errorlevel or np.err:
                err = 'Running (%s) failed: %s, %s.' % (cmdline, np.errorlevel,
                                                        np.err)
                raise Exception, err
            if np.out=='': #何も入ってない
                continue
            dom = parseString(np.out)
            root = dom.documentElement
            #estresult_node = root.getElementsByTagName("document")[0]
            element_array = root.getElementsByTagName("document")
            for element in element_array:
                url = ""
                title = ""
                date = 0
                detail = ""
                author = "不明"

                #detailを生成
                elem_array =  element.getElementsByTagName("snippet")
                detail = self._get_innerText("",elem_array)

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
                        attr_value = urllib.unquote(attr_value).encode('raw_unicode_escape').decode('CP932')
                        attr_value = attr_value[(len('file:///')+len(replace_left)):]
                        if browse_trac:
                            url = self.env.href.browser(url_left + attr_value)
                            title = "source:"+ urllib.unquote(url).encode('raw_unicode_escape').decode('utf-8')
                        else:
                            url = url_left + attr_value
                            title = urllib.unquote(url).encode('raw_unicode_escape').decode('utf-8')
                    #更新日時を生成
                    elif attr_name =="@mdate":
                        date = time.strptime(attr_value,"%Y-%m-%dT%H:%M:%SZ")
                        self.log.debug('date:%r', attr_value)
                        date = to_datetime(datetime(date[0],date[1],date[2],date[3],date[4],date[5],0,utc)) # for Trac0.11
                yield(url,title,date,to_unicode(author,'utf-8'),to_unicode(detail,'utf-8'))
        return

    #XMLのElementを再帰的に探してテキストを生成
    def _get_innerText(self,text,node_array):
        for node in node_array:
            if node.nodeType == node.TEXT_NODE:
                text = text + unicode(node.data).encode('utf-8')
            else:
                text = self._get_innerText(text,node.childNodes)
        return text


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
        estcmd_path = mod.estcmd_path
        estcmd_arg = mod.estcmd_arg
        estcmd_encode = mod.estcmd_encode

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

            #cmdline = "%s %s %s %s" % (estcmd_path,estcmd_arg,cs_index_path,unicode(query,'utf-8').encode('CP932'))
            qline = ' '.join(terms)
            cmdline = "%s %s %s %s" % (estcmd_path,estcmd_arg,cs_index_path,qline)
            self.log.debug('SearchChangesetHyperEstraier:%r', cmdline)
            cmdline = unicode(cmdline).encode(estcmd_encode)
            np = NaivePopen(cmdline)
            #self.log.debug('Result:%r', np.out)
            if np.errorlevel or np.err:
                err = 'Running (%s) failed: %s, %s.' % (cmdline, np.errorlevel,
                                                        np.err)
                raise Exception, err
            if np.out=='': #何も入ってない
                continue
            dom = parseString(np.out)
            root = dom.documentElement
            #estresult_node = root.getElementsByTagName("document")[0]
            element_array = root.getElementsByTagName("document")
            for element in element_array:
                url = ""
                title = ""
                date = 0
                detail = ""
                author = "不明"

                #detailを生成
                elem_array =  element.getElementsByTagName("snippet")
                detail = self._get_innerText("",elem_array)

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
                yield(url,title,date,to_unicode(author,'utf-8'),to_unicode(detail,'utf-8'))
        return

    #XMLのElementを再帰的に探してテキストを生成
    def _get_innerText(self,text,node_array):
        for node in node_array:
            if node.nodeType == node.TEXT_NODE:
                text = text + unicode(node.data).encode('utf-8')
            else:
                text = self._get_innerText(text,node.childNodes)
        return text


class SearchAttachmentHyperEstraierModule(Component):

    implements(ISearchSource)

    # ISearchProvider methods
    def get_search_filters(self, req):
        mod = SearchHyperEstraierModule(self.env)
        if mod.att_index_path:
            yield ('attachmenthyperest', u'he:添付ファイル', 0)

    def get_search_results(self, req, terms, filters):
        if not 'attachmenthyperest' in filters:
            return

        mod = SearchHyperEstraierModule(self.env)
        estcmd_path = mod.estcmd_path
        estcmd_arg = mod.estcmd_arg
        estcmd_encode = mod.estcmd_encode
        att_index_path = mod.att_index_path
        att_replace_left = os.path.join(os.path.normpath(self.env.path), 'attachments')

        #cmdline = "%s %s %s %s" % (estcmd_path,estcmd_arg,att_index_path,unicode(query,'utf-8').encode('CP932'))
        qline = ' '.join(terms)
        cmdline = "%s %s %s %s" % (estcmd_path,estcmd_arg,att_index_path,qline)
        self.log.debug('SearchHyperEstraier:%r', cmdline)
        cmdline = unicode(cmdline).encode(estcmd_encode)
        np = NaivePopen(cmdline)
        #self.log.debug('Result:%r', np.out)
        if np.errorlevel or np.err:
            err = 'Running (%s) failed: %s, %s.' % (cmdline, np.errorlevel,
                                                    np.err)
            raise Exception, err
        if not np.out:  #添付ファイルフォルダに何も入ってない
            return

        dom = parseString(np.out)
        root = dom.documentElement
        #estresult_node = root.getElementsByTagName("document")[0]
        element_array = root.getElementsByTagName("document")
        for element in element_array:
            url = ""
            title = ""
            date = 0
            detail = ""
            author = "不明"

            #detailを生成
            elem_array =  element.getElementsByTagName("snippet")
            detail = self._get_innerText("",elem_array)

            #その他の属性を生成
            attrelem_array = element.getElementsByTagName("attribute")
            for attrelem in attrelem_array:
                attr_name = attrelem.getAttribute("name")
                attr_value = unicode(attrelem.getAttribute("value")) #添付ファイルはパスがquoteされたものになっている
                #URLとタイトルを生成
                if attr_name == "_lreal":
                    attr_value=attr_value[len(att_replace_left):].replace("\\","/")
                    url = self.env.href.attachment("") #attachmentまでのurl取得
                    url = url +attr_value[1:] #[1:]は先頭の"/"を除くため
                    #そのままunquoteすると文字化けするから
                    title = urllib.unquote(attr_value).encode('raw_unicode_escape').decode('utf-8')
                    title = "attachment"+ title
                    title = title.replace("/",":")
                #更新日時を生成
                elif attr_name =="@mdate":
                    date = time.strptime(attr_value,"%Y-%m-%dT%H:%M:%SZ")
                    self.log.debug('date:%r', attr_value)
                    date = to_datetime(datetime(date[0],date[1],date[2],date[3],date[4],date[5],0,utc)) # for Trac0.11
            yield(url,title,date,to_unicode(author,'utf-8'),to_unicode(detail,'utf-8'))
        return

    #XMLのElementを再帰的に探してテキストを生成
    def _get_innerText(self,text,node_array):
        for node in node_array:
            if node.nodeType == node.TEXT_NODE:
                text = text + unicode(node.data).encode('utf-8')
            else:
                text = self._get_innerText(text,node.childNodes)
        return text


class SearchDocumentHyperEstraierModule(Component):

    implements(ISearchSource)

    # ISearchProvider methods
    def get_search_filters(self, req):
        mod = SearchHyperEstraierModule(self.env)
        if mod.doc_index_path and mod.doc_replace_left and mod.doc_url_left:
            yield ('documenthyperest', u'he:ドキュメント', 0)

    def get_search_results(self, req, terms, filters):
        if not 'documenthyperest' in filters:
            return

        mod = SearchHyperEstraierModule(self.env)
        estcmd_path = mod.estcmd_path
        estcmd_arg = mod.estcmd_arg
        estcmd_encode = mod.estcmd_encode
        doc_index_path = mod.doc_index_path
        doc_replace_left = mod.doc_replace_left
        doc_url_left = mod.doc_url_left

        #cmdline = "%s %s %s %s" % (estcmd_path,estcmd_arg,doc_index_path,unicode(query,'utf-8').encode('CP932'))
        qline = ' '.join(terms)
        cmdline = "%s %s %s %s" % (estcmd_path,estcmd_arg,doc_index_path,qline)
        self.log.debug('SearchHyperEstraier:%r', cmdline)
        cmdline = unicode(cmdline).encode(estcmd_encode)
        np = NaivePopen(cmdline)
        #self.log.debug('Result:%r', np.out)
        if np.errorlevel or np.err:
            err = 'Running (%s) failed: %s, %s.' % (cmdline, np.errorlevel,
                                                    np.err)
            raise Exception, err
        if np.out=='': #ドキュメントフォルダに何も入ってない
            return
        dom = parseString(np.out)
        root = dom.documentElement
        #estresult_node = root.getElementsByTagName("document")[0]
        element_array = root.getElementsByTagName("document")
        for element in element_array:
            url = ""
            title = ""
            date = 0
            detail = ""
            author = "不明"

            #detailを生成
            elem_array =  element.getElementsByTagName("snippet")
            detail = self._get_innerText("",elem_array)

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
                    attr_value = urllib.unquote(attr_value).encode('raw_unicode_escape').decode('CP932')
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
            yield(url,title,date,to_unicode(author,'utf-8'),to_unicode(detail,'utf-8'))
        return

    #XMLのElementを再帰的に探してテキストを生成
    def _get_innerText(self,text,node_array):
        for node in node_array:
            if node.nodeType == node.TEXT_NODE:
                text = text + unicode(node.data).encode('utf-8')
            else:
                text = self._get_innerText(text,node.childNodes)
        return text
