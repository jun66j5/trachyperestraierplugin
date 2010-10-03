# -*- coding: utf-8 -*-

import os
import time
import sys, string
from svn import core, fs, delta, repos
import codecs

#argvs[1]:repository path
#argvs[2]:changeset folder
#argvs[3]:start revision
#argvs[4]:end revision
argvs = sys.argv  #コマンドライン引数リスト
argc = len(argvs) #引数の個数

if (argc != 5):   #5でなければ出る
    usage(1)

path = argvs[1]
path = core.svn_path_canonicalize(path)
repos_ptr = repos.open(path)
fs_ptr = repos.fs(repos_ptr)

changeset_folder = argvs[2]

start_rev = int(argvs[3])
end_rev = int(argvs[4])

if start_rev>end_rev:
    sys.exit(exit)

rev = fs.youngest_rev(fs_ptr)
if start_rev>rev and end_rev>rev:
    sys.exit(exit)
  
if start_rev>rev:
    start_rev=rev
if end_rev>rev:
    end_rev=rev

for current_rev in range(start_rev,end_rev+1):
    #get comment log
    log = fs.revision_prop(fs_ptr, current_rev, core.SVN_PROP_REVISION_LOG) or ''
    
    #make dir
    folder_num = current_rev/1000
    file_folder = changeset_folder+'\\'+str(folder_num)
    if not os.path.exists(file_folder):
        os.makedirs(file_folder)
    #make file
    filename = file_folder+'\\'+str(current_rev)+'.txt'
    f = open(filename, 'w')
    f.write(log)
    f.close()
    #file update time
    date = fs.revision_prop(fs_ptr, current_rev, core.SVN_PROP_REVISION_DATE)
    aprtime = core.svn_time_from_cstring(date)
    secs = aprtime / 1000000  # aprtime is microseconds; make seconds
    timestr=time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime(secs))
    atime = mtime = time.mktime(time.strptime(timestr, '%Y-%m-%d-%H:%M:%S'))
    os.utime(filename, (atime, mtime))
