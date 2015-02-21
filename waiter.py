# This program runs in background and triggers runs of cook.py when a certain file is found.
# This allows ePubChef users to trigger eBook generation on a remote machine on which files are
# synced.
# The code is for running on ubuntu 14.

# The code will check for the existence of a file named waiter.txt in the current directory and
# all sibling directories. It then reads cook.py arguments from the first line of waiter.py, triggers
# the job, then comments out the waiter.txt arguments so as not to repeat the run.
# Logs are written to waiter.log.

import os
from os.path import isfile, join
import shutil
import subprocess
import time
import datetime
# presume this file strucure
# epubchef/waiter.py  (epubchef from github)
# Copy/ePubChef_1
# Copy/ePubChef_2
# Copy/ePubChef_n
#   where Copy folders are owned by info@epubchf.org Copy.com user
#   dirs within that have any name, but are epubchef copies

#   waiter.py will be run from epubchef dir and look for changes in the Copy/ePubChef/... dirs

run_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(run_dir, os.pardir, "custs"))
print("root_dir", root_dir)
root_log_loc = join(root_dir,'waiter_root.log')
root_log = open(root_log_loc, 'w')
root_log.write("The waiter has started.")

def list_dirs():
    # return a list of the current directory (where this scirpt was started and all
    # its sibling directories)
    dir_names = file_list = next(os.walk(root_dir))[1]
    full_dirs = []
    for dir in dir_names:
        full_dirs.append(join(root_dir, dir))
    dirs = full_dirs
    return dirs # for now

def find_and_run(a_directory):
    # test for presents of waiter.txt
    if os.path.exists(join(a_directory, 'waiter.txt')):
        print("waiter.txt exists")
        args = read_args(a_directory)
        if args[0][0] != '#':   # ignore if the line is commented out
            cook_loc = join(a_directory,'cook.py')
            log_loc = join(a_directory,'waiter.log')
            log = open(log_loc, 'w')
            log.write("The waiter has spotted you.")
            root_log.write("waiter processing: " + a_directory)
            get_fresh_cook(cook_loc)
            try:
                output = subprocess.check_output(['python3',cook_loc,args[0],args[1]], shell=False)
            except:
                # only one argument
                output = subprocess.check_output(['python3',cook_loc,args[0]], shell=False)
            rewrite_waiter(a_directory, args)
            log.close()
        else:
            print("commented out")
    else:
        print("No waiter.txt around")

def get_fresh_cook(cook_loc):
    # for security reasons, copy cook.py which came from github
    # rather than run what a user might have created.
    shutil.copy2(join(run_dir,'cook.py'), cook_loc)

def read_args(a_directory):
    try:
        f = open(join(a_directory, 'waiter.txt'), 'r')
        args = f.readlines()[0].strip().split(" ")
        print("args:", args)
        f.close()
    except:
        print("failed to read args")
        args=['#']
    return(args)

def rewrite_waiter(a_directory, args):
    # put a comment before the first line
    f = open(join(a_directory, 'waiter.txt'), 'w')
    output = '#'
    for item in args:
        output = output + item + " "
    f.write(output)
    output = "\n" + str(datetime.datetime.now())
    f.write(output)
    f.close()

######################################
# main processing
while True:
    dirs = list_dirs()
    for directory in dirs:
        find_and_run(directory)
    print("sleeping....")
    time.sleep(2)

root_log.close()
