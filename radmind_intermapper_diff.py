#!/usr/bin/python -tt

################################################################################
##                                                                            ##
## radmind_intermapper_diff.py                                                ##
##                                                                            ##
## This script takes the Radmind configuration file (default is ./config) and ##
## generates a list of just the IP addresses.  Then it takes the latest       ##
## InterMapper full device list and generates a list of just those IP         ##
## addresses.  Lastly, it puts the lists against one another to determine the ##
## disparity and reports this back to the user in an easily-readable format.  ##
##                                                                            ##
################################################################################
##                                                                            ##
## DETAILED USAGE INSTRUCTIONS                                                ##
##                                                                            ##
## Command-line options available:                                            ##
##                                                                            ##
##   -h : display help information and quit                                   ##
##   -v : display version information and quit                                ##
##   -f : give full output (prints all addresses)                             ##
##   -q : suppress output to the console (nice for file output)               ##
##   -x : lists all declared variables at the beginning of runtime            ##
##   -E : list all built-in exclusions and quit                               ##
##                                                                            ##
##   -i 'file' : use 'file' as InterMapper address list                       ##
##   -r 'file' : use 'file' as Radmind config file                            ##
##   -o 'file' : use 'file' as the output destination file                    ##
##               Note: there is still console output by default!              ##
##                                                                            ##
##   -s # : only print one set of results:                                    ##
##      1 : Radmind                                                           ##
##      2 : InterMapper                                                       ##
##                                                                            ##
################################################################################
##                                                                            ##
## COPYRIGHT (c) 2014 Marriott Library IT Services.  All Rights Reserved.     ##
##                                                                            ##
## Author:          Pierce Darragh - pierce.darragh@utah.edu                  ##
## Creation Date:   November 18, 2013                                         ##
## Last Updated:    January  17, 2014                                         ##
##                                                                            ##
## Permission to use, copy, modify, and distribute this software and its      ##
## documentation for any purpose and without fee is hereby granted, provided  ##
## that the above copyright notice appears in all copies and that both that   ##
## copyright notice and this permission notice appear in supporting           ##
## documentation, and that the name of The Marriott Library not be used in    ##
## advertising or publicity pertaining to distribution of the software        ##
## without specific, written prior permission. This software is supplied as-  ##
## is without expressed or implied warranties of any kind.                    ##
##                                                                            ##
################################################################################

## IMPORTS
import argparse
import sys
import re
import subprocess
import getpass
import urllib2

## DEFINE GLOBAL VARIABLES
def set_gvars ():
    # REGEX PATTERNS
    global IP_PATTERN   # Generic IP address

    IP_PATTERN = re.compile('[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+')

    # COLORS
    global RS       # Reset color settings
    global FBRED    # Foreground bright red
    global FBGRN    # Foreground bright green
    global FBYEL    # Foreground bright yellow
    global FBCYN    # Foreground bright cyan
    global CARET    # Carriage return

    RS = "\033[0m"
    FBRED = "\033[1;91m"
    FBGRN = "\033[1;92m"
    FBYEL = "\033[1;93m"
    FBCYN = "\033[1;96m"
    CARET = "\r\033[K"

    # ADDRESSES
    # Change these for your local environment!  It'll make your life easier.
    global RADMIND_CONFIG       # Default location of Radmind config file
    global INTERMAPPER_ADDRESS  # Default web address of InterMapper full list
    global INTERMAPPER_DEFAULT  # Default local location for InterMapper list

    RADMIND_CONFIG = "/radmind_server_root/radmind/config"
    INTERMAPPER_ADDRESS = "https://intermapper.address/~admin/full_screen.html"
    INTERMAPPER_DEFAULT = "./intermapper_list.html"

    # OTHER
    # DON'T CHANGE THESE
    global VERSION      # Current version of the script

    VERSION = "1.8.0"

## MAIN
def main ():
    print " " * 80 + "|"
    set_gvars()

    parse_options()

    rm_list = get_radmind()

    im_list = get_intermapper()

    if explicit:
        print "\nThese variables were used:"
        print "\t{:10} : {}".format('full', full)
        print "\t{:10} : {}".format('quiet', quiet)
        print "\t{:10} : {}".format('im_file', im_file)
        print "\t{:10} : {}".format('im_address', im_address)
        print "\t{:10} : {}".format('rm_file', rm_file)
        print "\t{:10} : {}".format('out_file', out_file)

## RADMIND ADDRESSES
def get_radmind ():
    matches = []
    prompt = ("Getting Radmind list from " + FBCYN + "[" + rm_file + "]" + RS
              + "...")

    print prompt,
    try:
        with open(rm_file) as f:
            for line in f:
                match = IP_PATTERN.search(line)
                if match:
                    matches.append(match.group())
        print CARET,
        pretty_print (prompt, 0)
        return matches
    except IOError:
        print CARET,
        pretty_print (prompt, 1)
        print (FBRED + "ERROR:" + RS + " The file" + FBCYN + "'" + rm_file +
               "'" + RS + " could not be opened.  Quitting...")
        sys.exit(1)

## INTERMAPPER ADDRESSES
# If InterMapper denies whitelist authentication.
def im_authenticate ():
    username = raw_input("InterMapper Username: ")
    password= getpass.getpass("InterMapper Password: ", stream=sys.stderr)

    password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()

    password_mgr.add_password(None, im_address, username, password)

    handler = urllib2.HTTPBasicAuthHandler(password_mgr)

    opener = urllib2.build_opener(handler)

    opener.open(address)

    urllibe2.install_opener(opener)

    # Need a loop in here somewhere...

def get_intermapper ():
    prompt = ("Getting InterMapper list from " + FBCYN + "[" + im_file + "]"
              + RS + "...")

    print prompt,
    try:
        page = urllib2.urlopen(im_address).read()
        matches = IP_PATTERN.findall(page)
        print CARET,
        pretty_print (prompt, 0)
        return matches
    except urllib2.HTTPError as e:
        print CARET,
        pretty_print (prompt, 1)
        print (FBYEL + "HTTP Error", e.code)
        print (RS + "You are not authorized to access " + FBCYN + "'"
               + im_address + "'" + RS + ".")
        print "Attempting authentication..."
        im_authenticate()
    except urllib2.URLError as e:
        print CARET,
        pretty_print (prompt, 1)
        print (FBRED + "ERROR:" + RS + " The address " + FBCYN + "'"
               + im_address + "'" + RS + " could not be accessed.")
        print "Reason:", e.reason
        sys.exit(1)


## PARSE FOR OPTIONS
def parse_options ():
    # Add arguments to the parser.
    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--version",
                        help="display the current version and quit",
                        action="store_true")
    parser.add_argument("-f", "--full",
                        help="gives full output",
                        action="store_true")
    parser.add_argument("-q", "--quiet",
                        help="don't output the lists",
                        action="store_true")
    parser.add_argument("-x", "--explicit",
                        help="show all declared variables at run-time",
                        action="store_true")

    parser.add_argument("-i", "--intermapper_file",
                        help="use 'file' as InterMapper file",
                        metavar='\'file\'',
                        dest='im_file',
                        default=INTERMAPPER_DEFAULT)
    parser.add_argument("-I", "--intermapper_address",
                        help="use 'address' to get InterMapper list",
                        metavar='\'address\'',
                        dest='im_address',
                        default=INTERMAPPER_ADDRESS)
    parser.add_argument("-r", "--radmind_file",
                        help="use 'file' as Radmind config file",
                        metavar='\'file\'',
                        dest='rm_file',
                        default=RADMIND_CONFIG)
    parser.add_argument("-o", "--output",
                        help="use 'file' to record results",
                        metavar='\'file\'',
                        dest='out_file',
                        default="")

    # Make all arguments globally accessible
    globals().update(vars(parser.parse_args()))

    # -v: Display version information and quit
    if version:
        print "%s" % VERSION
        sys.exit(0)

## PROPER SPACING FOR RESULTS
def pretty_print (s, i):
    if len(s) < 70:
        if i == 0:
            print "\b" + s + " " * (85 - len(s)) + FBGRN + "[done]" + RS
        elif i == 1:
            print "\b" + s + " " * (83 - len(s)) + FBRED + "[failed]" + RS
        else:
            print "\b" + " " * (91 - len(s)) + s
    else:
        print "\b" + s
        if i == 0:
            print " " * 74 + FBGRN + "[done]" + RS
        elif i == 1:
            print " " * 72 + FBRED + "[failed]" + RS

## CALL TO MAIN
if __name__ == "__main__":
    main()

