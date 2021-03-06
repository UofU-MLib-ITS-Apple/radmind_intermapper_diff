#!/usr/bin/python -tt

'''
################################################################################

radmind_intermapper_diff.py

This script takes the Radmind configuration file (default is ./config) and
generates a list of just the IP addresses.  Then it takes the latest InterMapper
full device list and generates a list of just those IP addresses.  Lastly, it
puts the lists against one another to determine the disparity and reports this
back to the user in an easily-readable format.

################################################################################

DETAILED USAGE INSTRUCTIONS

Optional arguments:

  -h : display help information and quit
  -v : display version information and quit
  -f : give full output (prints all addresses)
  -q : suppress output to the console (nice for autmated runnings)
  -x : lists all declared variables at the beginning of runtime
  -d : leaves the full DNS names intact (shortname.other.stuff.here)
  -e : specifies whether to send an email (usually used for defaults)

  -r 'file'     : use 'file' as Radmind config file
  -i 'file'     : use 'file' as InterMapper address list
  -I 'address'  : use 'address' as InterMapper web address
  -o 'file'     : use 'file' as the output destination file
                  Note: there is still console output by default!

  --smtp-server 'address'   : use 'address' as the smtp server for sending mail
  --email-address 'address' : use 'address' as the recipient of the email
  --source-email 'address'  : use 'address' as the sender of the email

Usage examples:

%(PROG)s -r config.txt -I "https://intermapper.domain.com"

    Fetches the Radmind config from 'config.txt' and the InterMapper list from
    'https://intermapper.domain.com'.  This will output the list of differences
    and then quit.

%(PROG) -r config.txt -i intermapper.txt -o output.txt

    Gets the InterMapper list from 'intermapper.txt' instead of online.  The
    list of differences is then outputted to 'output.txt' as well as to the
    console.

%(PROG) -r config.txt -i intermapper.txt -o output.txt -qe

    After finding the differences, this will suppress console output (the user
    will not see anything), but will place the output into a text file
    'output.txt' and then attempt to email the list using the default email
    settings.

%(PROG) -r config.txt -i intermapper.txt --smtp-server "smtp.domain.com"
  --email-address "recipient@domain.com" --source-email "PROG@domain.com" -qdx

    After finding the differences, this will suppress console output.  The list
    will be send via email from 'PROG@domain.com' to 'recipient@domain.com'
    using the SMTP server 'smtp.domain.com'.  The DNS mappings will be left in
    their unaltered states ('computer.tech.domain.com' vs 'computer'), and the
    program will display a list of all variables used at the beginning of
    execution.

UNIMPLEMENTED OPTIONS (TO-DO)
  -E : list all built-in exclusions and quit
  -s # : only print one set of results:
     1 : Radmind
     2 : InterMapper

################################################################################

COPYRIGHT (c) 2014 Marriott Library IT Services.  All Rights Reserved.

Author:          Pierce Darragh - pierce.darragh@utah.edu
Creation Date:   November 18, 2013
Last Updated:    February 11, 2014

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee is hereby granted, provided that
the above copyright notice appears in all copies and that both that copyright
notice and this permission notice appear in supporting documentation, and that
the name of The Marriott Library not be used in advertising or publicity
pertaining to distribution of the software without specific, written prior
permission. This software is supplied as-is without expressed or implied
warranties of any kind.

################################################################################
'''

'''
################################################################################
IMPORTS
################################################################################
'''
import argparse
import getpass
import datetime
import logging
import math
import os
import re
import smtplib
import socket
import subprocess
import sys
import textwrap
import traceback
import urllib2

from email.mime.text import MIMEText

'''
################################################################################
DEFINE GLOBAL VARIABLES

    A few variables are used throughout this script, and they are defined here.
################################################################################
'''
def set_gvars ():
    ''' USER CONFIGURABLE '''
    '''###################'''
    # Change these for your local environment!  It'll make your life easier.
    global RADMIND_CONFIG       # Default location of Radmind config file
    global INTERMAPPER_ADDRESS  # Default web address of InterMapper full list
    global SMTP_SERVER          # Default SMTP server address
    global DESTINATION_EMAIL    # Default send-to address for email
    global SOURCE_EMAIL         # Default sent-from address for email
    global LOG_PATH             # Location where the log will be written
    global LOG_FILE             # The name of the actual log file

    RADMIND_CONFIG      = "/radmind_server_root/radmind/config"
    INTERMAPPER_ADDRESS = "https://intermapper.address/~admin/full_screen.html"
    SMTP_SERVER         = "smtp@yourdomain"
    DESTINATION_EMAIL   = "root@localhost"
    SOURCE_EMAIL        = "radmind_intermapper_diff.py@localhost"
    LOG_PATH            = "/var/log/"
    LOG_FILE            = "radmind_intermapper_diff.log"

    ''' DON'T CHANGE THESE UNLESS YOU KNOW WHAT YOU'RE DOING!!! '''
    '''#########################################################'''
    # REGEX PATTERNS
    global IP_PATTERN   # Generic IP address
    global RM_PATTERN   # Radmind shorthand addresses: a.b.c.<d-e>
    global RM_3         # Radmind three-deep match: 'a.b.c.'
    global RM_FIRST     # Radmind first match: d in a.b.c.<d-e>
    global RM_LAST      # Radmind last match: e in a.b.c.<d-e>

    IP_PATTERN  = re.compile('\d+\.\d+\.\d+\.\d+')
    RM_PATTERN  = re.compile('\d+\.\d+\.\d+\.[^\s)]+')
    RM_3        = re.compile('\d+\.\d+\.\d+\.')
    RM_FIRST    = re.compile('<(\d+)')
    RM_LAST     = re.compile('(\d+)>')

    # OTHER
    # DON'T CHANGE THESE
    global VERSION      # Current version of the script
    global OUTPUT_TEXT  # Stores all the text (so it can be outputted multiple
                        # times easily)

    VERSION     = "2.2.4"
    OUTPUT_TEXT = ''


'''
################################################################################
USAGE

    The -h and --help options will display useful information on the various
    options available to the user.

    Primarily this function exists so that I can exert control over the
    formatting of the output, since I didn't like how argparse handled the
    output by default.
################################################################################
'''
def usage (quit_code=0):
    name = os.path.basename(__file__)
    print name + " " + VERSION

    if version:
        sys.exit(0)

    description = '''Finds the IP addresses that exist in a Radmind
configuration file and an InterMapper report and then determines the
disparity between the two.  This information is then reported back to the
user, and can optionally be stored in a text file or emailed.'''

    desc = textwrap.fill(textwrap.dedent(description).strip(),
                         initial_indent='  ',
                         subsequent_indent='  ',
                         width=80)

    switches = []
    switches.append(['-h, --help', "show this help message and exit"])
    switches.append(['-v, --version', "display the current version and exit"])
    switches.append(['-V, --verbose', "increase logging verbosity"])
    switches.append(['-f, --full', "give full output"])
    switches.append(['-q, --quiet', "suppress console output"])
    switches.append(['-x, --explicit', "show all declared variables at run-time (overrides -q)"])
    switches.append(['-d, --dns-full', "leave the full DNS names intact"])
    switches.append(['-e, --email', "send an email to the default address"])

    switches_length = 0
    for item in switches:
        if len(item[0]) > switches_length:
            switches_length = len(item[0])

    positionals = []
    positionals.append(['-r, --radmind-file \'file\'', "use 'file' as the Radmind configuration file"])
    positionals.append(['-i, --intermapper-file \'file\'', "use 'file' as the InterMapper list of addresses"])
    positionals.append(['-I, --intermapper-address \'address\'', "use 'address' as the InterMapper connection address (to get freshest results)"])
    positionals.append(['-o, --output \'file\'', "output the results to 'file'"])
    positionals.append(['    --smtp-server \'address\'', "set the SMTP server to 'address' (for sending mail)"])
    positionals.append(['    --email-address \'address\'', "send output in an email to 'address'"])
    positionals.append(['    --source-email \'address\'', "send output in an email from 'address'"])
    positionals.append(['    --log-path \'path\'', "send logging output to a file in 'path'"])

    positionals_length = 0
    for item in positionals:
        if len(item[0]) > positionals_length:
            positionals_length = len(item[0])

    examples = []
    examples.append([name + ' -r config.txt -I "https://intermapper.domain.com"',
        '''Fetches the Radmind config from 'config.txt' and the InterMapper list
        from 'https://intermapper.domain.com'.  This will output the list of
        differences and then quit.'''])
    examples.append([name + ' -r config.txt -i intermapper.txt -o output.txt',
        '''Gets the InterMapper list from 'intermapper.txt' instead of online.
        The list of differences is then outputted to 'output.txt' as well as to
        the console.'''])
    examples.append([name + ' -r config.txt -i intermapper.txt -o output.txt -qe',
        '''After finding the differences, this will suppress console output (the
        user will not see anything), but will place the output into a text file
        'output.txt' and then attempt to email the list using the default email
        settings.'''])
    examples.append([name + ''' -r config.txt -i intermapper.txt --smtp-server "smtp.domain.com"
--email-address "recipient@domain.com" --source-email "PROG@domain.com" -qdx''',
        '''After finding the differences, this will suppress console output.
        The list will be send via email from 'PROG@domain.com' to
        'recipient@domain.com' using the SMTP server 'smtp.domain.com'.  The DNS
        mappings will be left in their unaltered states
        ('computer.tech.domain.com' vs 'computer'), and the program will display
        a list of all variables used at the beginning of execution.'''])

    print desc
    print

    print "Optional arguments:"
    for item in switches:
        print "  {0:<{1}}  {2}".format(item[0], switches_length, item[1])
    print
    for item in positionals:
        print "  {0:<{1}} ".format(item[0], positionals_length),

        new_width = 80 - positionals_length - 4
        text = textwrap.fill(textwrap.dedent(item[1]).strip(),
                                  initial_indent='',
                                  subsequent_indent='',
                                  width=new_width)
        lines = []
        for line in text.split('\n'):
            lines.append(line)
        print lines[0]
        for i in range (1, len(lines)):
            print "{0:<{1}}{2}".format('', new_width - 2, lines[i])

    print
    print "Usage examples:"
    for item in examples:
        instruction = textwrap.fill(textwrap.dedent(item[0]).strip(),
                            initial_indent='',
                            subsequent_indent='  ',
                            width=80)
        text = textwrap.fill(textwrap.dedent(item[1]).strip().strip('   '),
                            initial_indent='    ',
                            subsequent_indent='    ',
                            width=80)
        print
        print instruction
        print
        print text

    sys.exit(quit_code)

'''
################################################################################
MAIN

    Program overview:
    1.      Initialization
    1.1.      Set the global variables
    1.2.      Parse for command line options
    1.3.      Build logging systems
    2.      Get address lists
    2.1.      Radmind addresses
    2.2.      InterMapper addresses
    3.      Get hostnames for IPs
    3.1.      Radmind hostnames
    3.2.      InterMapper hostnames
    4.      Sort IP addresses
    4.1.      Radmind addresses
    4.2.      InterMapper addresses
    5.      Find disparities
    5.1.      Radmind positive disparity (Radmind has, InterMapper doesn't)
    5.2.      InterMapper positive dispairty (InterMapper has, Radmind doesn't)
    6.      File output
    7.      Email output
    8.      Console output
################################################################################
'''
def main ():
    # Initialization
    set_gvars()
    parse_options()
    build_loggers()

    # Get the list of Radmind IPs
    rm_list = get_radmind()

    # Get the list of InterMapper IPs
    # If the user specifies a file to get them from, use that.  Otherwise,
    # attempt to connect to im_address and use a new version.
    if im_file:
        im_list = get_intermapper_file()
    else:
        im_list = get_intermapper_web()

    # Get the hostnames for Radmind IPs
    rm_stuff = {}
    for i in range(0, len(rm_list)):
        update_progress(i/float(len(rm_list)))
        item = rm_list[i]
        rm_stuff[item] = str(get_host(item)).replace("'", "")
    update_progress()
    logger.info("Radmind hostnames acquired.")

    # Get the hostnames for InterMapper IPs
    im_stuff = {}
    for i in range(0, len(im_list)):
        update_progress(i/float(len(im_list)))
        item = im_list[i]
        im_stuff[item] = str(get_host(item)).replace("'", "")
    update_progress()
    logger.info("InterMapper hostnames acquired.")

    '''
    Sort the IP addresses.

    The following sort method was detailed in an answer by Ferdinand Beyer to
    the question "How to sort IP addresses stored in dictionary in Python?" at:
        http://stackoverflow.com/questions/6545023/how-to-sort-ip-addresses-
        stored-in-dictionary-in-python
    It returns the values with the IP addresses sorted properly, and keeps
    their hostnames attached.
    '''
    rm_sorted = []
    im_sorted = []
    try:
        rm_sorted = sorted(rm_stuff.items(),
                           key=lambda item: socket.inet_aton(item[0]))
        im_sorted = sorted(im_stuff.items(),
                           key=lambda item: socket.inet_aton(item[0]))
    except:
        logger.error("IP sorting failed")
        traceback.print_exc(file=sys.stdout)
    logger.info("IP addresses sorted.")

    # Find the Radmind positive disparities
    rm_diff = differences(rm_sorted, im_sorted)
    logger.info("Found Radmind positive disparity.")
    # Find the InterMapper positive disparities
    im_diff = differences(im_sorted, rm_sorted)
    logger.info("Found InterMapper positive disparity.")

    prep_output (rm_diff, im_diff)

    if out_file:
        file_output ()

    if email:
        send_email ()

    if not quiet:
        print "\n"
        if full:
            prep_output (rm_sorted, im_sorted)
            print (OUTPUT_TEXT)
        else:
            print (OUTPUT_TEXT)

'''
################################################################################
PARSE ARGUMENTS

    This takes in any command-line arguments and interprets them appropriately.
    Valid options include:
        -h, --help
        -v, --version
        -V, --verbose
        -f, --full
        -q, --quiet
        -x, --explicit
        -d, --dns-full
        -e, --email

        -r, --radmind-file 'file'
        -i, --intermapper-file 'file'
        -I, --intermapper-address 'address'
        -o, --output 'file'
            --smtp-server
            --email-address
            --source-email
            --log-path
################################################################################
'''
def parse_options ():
    # Add arguments to the parser.
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("-h", "--help",
                        action='store_true')
    parser.add_argument("-v", "--version",
                        action='store_true')
    parser.add_argument("-V", "--verbose",
                        dest='verbosity',
                        action="count")
    parser.add_argument("-f", "--full",
                        action="store_true")
    parser.add_argument("-q", "--quiet",
                        action="store_true")
    parser.add_argument("-x", "--explicit",
                        action="store_true")
    parser.add_argument("-d", "--dns-full",
                        dest='dns_full',
                        action="store_true")
    parser.add_argument("-e", "--email",
                        dest='email',
                        action='store_true')

    parser.add_argument("-r", "--radmind-file",
                        dest='rm_file',
                        default=RADMIND_CONFIG)
    parser.add_argument("-i", "--intermapper-file",
                        dest='im_file',
                        default=None)
    parser.add_argument("-I", "--intermapper-address",
                        dest='im_address',
                        default=INTERMAPPER_ADDRESS)
    parser.add_argument("-o", "--output",
                        dest='out_file',
                        default=None)
    parser.add_argument("--smtp-server",
                        dest='smtp_server',
                        default=SMTP_SERVER)
    parser.add_argument("--email-address",
                        dest='destination_email',
                        default=DESTINATION_EMAIL)
    parser.add_argument("--source-email",
                        dest='source_email',
                        default=SOURCE_EMAIL)
    parser.add_argument("--log-path",
                        dest='log_dest',
                        default=LOG_PATH)

    # Make all arguments globally accessible
    globals().update(vars(parser.parse_args()))

    # If the user specified the explicit option, show all of the variables used.
    if explicit:
        print
        print '-' * 80
        print "These variables were used:"
        print "  {:20} : {}".format('verbosity', verbosity)
        print "  {:20} : {}".format('full', full)
        print "  {:20} : {}".format('quiet', quiet)
        print "  {:20} : {}".format('explicit', explicit)
        print "  {:20} : {}".format('dns_full', dns_full)
        print "  {:20} : {}".format('email', email)

        print "  {:20} : {}".format('rm_file', rm_file)
        print "  {:20} : {}".format('im_file', im_file)
        print "  {:20} : {}".format('im_address', im_address)
        print "  {:20} : {}".format('out_file', out_file)
        print "  {:20} : {}".format('smtp_server', smtp_server)
        print "  {:20} : {}".format('destination_email', destination_email)
        print "  {:20} : {}".format('source_email', source_email)
        print "  {:20} : {}".format('log_dest', log_dest)
        print '-' * 80
        print

    if help:
        usage()
        sys.exit(0)

'''
################################################################################
LOGGING SET-UP

    Creates the logger to be used throughout.  One logger is created which
    streams its information to the console, and the other writes to a file.
################################################################################
'''
def build_loggers ():
    # If the logging destination path doesn't end in a slash... fix it.
    global log_dest
    if not log_dest.endswith('/'):
        log_dest = log_dest + '/'

    # Set the file logging verbosity.
    if verbosity == 0:
        file_logging_level = logging.INFO
    elif verbosity == 1:
        file_logging_level = logging.DEBUG
    elif verbosity > 1:
        file_logging_level = 0
    else:
        file_logging_level = logging.INFO

    # Set the console logging verbosity.
    if quiet:
        console_logging_level = logging.WARNING
    else:
        console_logging_level = logging.INFO

    # Create the root logger.  These are the settings for console output.
    logging.basicConfig(level=console_logging_level, format='%(message)s')
    global logger
    logger = logging.getLogger(__name__)

    # Check if we have write permissions to the directory.  If not, don't write
    # the logs out to a file.  If yes, write to the file and output simplified
    # information to the console.
    if os.access(log_dest, os.W_OK):
        # Prepends with a line and the date.  Useful for searching through the
        # log file.
        nfh = logging.FileHandler(log_dest + LOG_FILE, mode='a')
        nfh_formatter = logging.Formatter('%(message)s')
        nfh.setFormatter(nfh_formatter)
        logger.addHandler(nfh)
        date = datetime.datetime.now().strftime('%a %b %d at %H:%M %Y')
        logger.info("-" * 80)
        logger.info(date)
        logger.removeHandler(nfh)

        # Set the file output handler appropriately now.
        fh = logging.FileHandler(log_dest + LOG_FILE, mode='a')
        fh_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        fh.setFormatter(fh_formatter)
        fh.setLevel(file_logging_level)
        logger.addHandler(fh)
    else:
        print "Logging will not be outputted to a file.  Check your variables."

'''
################################################################################
GET HOSTNAME

    Takes an IP address and attempts to find a valid hostname for that address.
    If none is found, False is stored in its place.
################################################################################
'''
def get_host (ip):
    try:
        data = socket.gethostbyaddr(ip)
        host = repr(data[0])
        if dns_full:
            hostname = host
        else:
            hostname = host.split('.')[0]
        logging.debug(ip + " => " + hostname)
        return hostname
    except Exception:
        logging.debug(ip + " => ")
        return False

'''
################################################################################
RADMIND FILE

    Scans the Radmind config file (usually located at /var/radmind/config) and
    records all of the IP addresses that appear at the beginnings of lines, and
    then returns those as a list.
################################################################################
'''
## RADMIND ADDRESSES
def get_radmind ():
    matches = []
    prompt = "Getting Radmind list from [" + rm_file + "]..."

    pretty_print (prompt)
    legit_file (rm_file, "rm", prompt)
    addresses = []
    with open(rm_file) as f:
        for line in f:
            result = RM_PATTERN.match(line)
            if result:
                addresses.append(result.group(0))

    for item in addresses:
        first = RM_FIRST.findall(item)
        if first:
            base = RM_3.findall(item)
            last = RM_LAST.findall(item)
            for x in range (int(first[0]), int(last[0]) + 1):
                full = base[0] + str(x)
                matches.append(full)
                logging.debug("Radmind matches += " + full)
        else:
            if not re.search('-', item):
                matches.append(item)
                logging.debug("Radmind matches += " + item)

    pretty_print (prompt, 1)

    logger.info("Got Radmind list from [" + rm_file + "].")
    return matches

'''
################################################################################
INTERMAPPER FILE

    In the event that a file is specified which contains all of the IP addresses
    for InterMapper, this will try to record them all.
################################################################################
'''
def get_intermapper_file ():
    matches = []
    prompt = "Getting InterMapper list from [" + im_file + "]..."

    pretty_print (prompt)

    legit_file (im_file, "im", prompt)
    with open(im_file) as f:
        matches = IP_PATTERN.findall(f.read())
        for item in matches:
            logging.debug("InterMapper matches += " + item)
        pretty_print (prompt, 1)

    logger.info("Got InterMapper list from [" + im_file + "].")
    return matches

'''
################################################################################
INTERMAPPER WEB

    InterMapper has a webpage with all of the IP addresses for its monitored
    devices.  Try to access that page and return a list containing all of those
    IP addresses
################################################################################
'''
def get_intermapper_web ():
    prompt = "Getting InterMapper list from [" + im_address + "]..."
    matches = []

    pretty_print (prompt)
    while True:
        try:
            page = urllib2.urlopen(im_address).read()
            pretty_print (prompt, 1)
            break;
        except urllib2.HTTPError as e:
            logger.warning("Issue authorizing to [" + im_address + "].")
            logger.warning("HTTP Error " + str(e.code))
            pretty_print (prompt, 2)
            message = "Not authorized to access the addres: [" + im_address + "]"
            pretty_print (message)
            im_authenticate()
        except urllib2.URLError as e:
            logger.error("Could not connect to [" + im_address + "].")
            logger.error("Reason: " + str(e.reason))
            pretty_print (prompt, 2)
            message = "Error:  The address could not be accessed."
            pretty_print (message)
            sys.exit(10)
        except Exception as e:
            logger.error("Could not connect to [" + im_address + "].")
            pretty_print (prompt, 2)
            print e
            sys.exit(10)

    matches = IP_PATTERN.findall(page)
    logger.info("Got InterMapper list from [" + im_address + "].")
    return matches

'''
################################################################################
INTERMAPPER AUTHENTICATION

    If InterMapper denies whitelist authentication (say, because you aren't on
    the appropriate network), you may be able to attempt HTTPS authentication.
    This attempts that authentication, as per the method described in the Python
    documentation.
################################################################################
'''
def im_authenticate ():
    # Get username and password from the user.
    print "Please provide credentials."
    username = raw_input("  InterMapper Username: ")
    password= getpass.getpass("  InterMapper Password: ", stream=sys.stderr)
    prompt = "Attempting authentication..."
    pretty_print (prompt)

    # The following is the recommended method of authenticating to a secure
    # website, as per the Python documentation at the time of this writing.
    try:
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, im_address, username, password)
        handler = urllib2.HTTPBasicAuthHandler(password_mgr)
        opener = urllib2.build_opener(handler)
        opener.open(im_address)
        urllib2.install_opener(opener)
        pretty_print(prompt, 1)
    except:
        pretty_print(prompt, 2)
        logger.error("InterMapper authentication failed.")
        sys.exit(11)
    logger.info("Authented to [" + im_address + "].")

'''
################################################################################
FIND DISPARITY

    Takes in two dictionaries, which are assumed to be formatted as:
        {IP_Address, hostname}
    and finds out which items exist in the first list, but not the second.
################################################################################
'''
def differences (positive, negative):
    different = []
    for i in range (0, len(positive)):
        update_progress(i/float(len(positive)))
        if not (compare (positive[i][0], negative)):
            different.append(positive[i])
    update_progress()
    return different

def compare (value, list):
    for other in list:
        if value == other[0]:
            return True
    return False

'''
################################################################################
PREPARE OUTPUT

    Outputs the given lists in order, with their IP addresses and hostnames
    spaced out for easy reading.  Any IP addresses with empty hostnames will
    display "No DNS Entry" (optionally in yellow).
################################################################################
'''
def prep_output (list1, list2):
    global OUTPUT_TEXT
    OUTPUT_TEXT = "Radmind items (" + str(len(list1)) + "):"
    for item in list1:
        if not item[1] == "False":
            OUTPUT_TEXT += "\n  {0:<{1}} {2}".format(item[0], (22), item[1])
        else:
            OUTPUT_TEXT += "\n  {0:<{1}} {2}".format(item[0], (22), "")

    OUTPUT_TEXT += '\n'
    OUTPUT_TEXT += "\nInterMapper items (" + str(len(list2)) + "):"
    for item in list2:
        if not item[1] == "False":
            OUTPUT_TEXT += "\n  {0:<{1}} {2}".format(item[0], (22), item[1])
        else:
            OUTPUT_TEXT += "\n  {0:<{1}} {2}".format(item[0], (22), "")

'''
################################################################################
OUTPUT TO FILE

    If the user specifies the '-o' option for output, this handles the
    formatting and writing of that file.
################################################################################
'''
# def file_output (list1, list2):
def file_output ():
    prompt = "Outputting to file [" + out_file + "]..."
    pretty_print (prompt)

    try:
        sys.stdout = open (out_file, 'w')
    except IOError as e:
        logger.error("Error writing to file: " + e.strerror)
        pretty_print (prompt, 2)
        sys.exit(21)
    date = datetime.datetime.now().strftime('%Y-%m-%d at %X %Z')
    print "Generated " + date
    print
    print OUTPUT_TEXT
    sys.stdout = sys.__stdout__
    pretty_print (prompt, 1)
    logger.info("Output to file [" + out_file + "].")

'''
################################################################################
EMAIL RESULTS

    Sends the results (as they would appear in file_output()) to the email
    address specified in email_address.
################################################################################
'''
def send_email ():
    prompt = "Sending email to [" + destination_email + "]..."
    pretty_print (prompt)

    # Get date
    short_date = datetime.datetime.now().strftime('%A, %B %d')
    full_date = datetime.datetime.now().strftime('%Y-%m-%d at %X %Z')

    # Create message container
    msg = MIMEText("Generated " + full_date + "\n\n" + OUTPUT_TEXT)
    msg['Subject'] = "Radmind/Intermapper Differences " + short_date
    msg['From'] = source_email
    msg['To'] = destination_email

    try:
        s = smtplib.SMTP(smtp_server)
        s.sendmail(msg['From'], [msg['To']], msg.as_string())
        s.quit
        pretty_print (prompt, 1)
    except socket.error as e:
        pretty_print (prompt, 2)
        logger.error("Could not send email.")
        logger.error(str(e))
        sys.exit(30)
    logger.info(("Sent output via email.\n"
                 + "{0:24}\tSMTP: " + smtp_server + "\n"
                 + "{0:24}\tFrom: " + source_email + "\n"
                 + "{0:24}\tTo:   " + destination_email).format(''))

'''
################################################################################
CHECK FILE LEGITIMACY

    To ensure that any of the specified files to be used are actually valid, we
    try to open them up.  If it works, return.  Otherwise, give the error
    message and quit.
################################################################################
'''
def legit_file (location, switch, prompt = ''):
    try:
        with open(location) as f:
            return
    except IOError as e:
        logger.error("Unable to open file [" + location + "].")
        logger.error("Error " + e.strerror)
        if prompt:
            pretty_print (prompt, 2)
        if switch == "im":
            logger.error("Try using the [-i] switch to specify the file manually.")
        elif switch == "rm":
            logger.error("Try using the [-r] switch to specify the file manually.")
        sys.exit(20)

'''
################################################################################
PROPER SPACING FOR FORMATTING

    The proper way to use this method is to first create a string to hold your
    message; we'll call ours MESSAGE.  Then do:
        pretty_print (MESSAGE)
    This sets up the formatting by outputting the text, without inserting a
    newline at the end.  Then call:
        pretty_print (MESSAGE, 1)        // or 2 for [failed]
    This will append the "[done]" message, right-aligned at 80 characters.
################################################################################
'''
def pretty_print (s, i = 0):
    # If we're being quiet, just don't do anything.
    if quiet:
        return
    # Create the wrapped text.
    # By default, it will wrap at 70 characters.
    dedented_text = textwrap.dedent(s).strip()
    text = textwrap.fill(dedented_text,
                         initial_indent='',
                         subsequent_indent='    ')
    # The text gets put in this array so we can find the length of the last
    # line to properly format the "[done]" and "[failed]" messages.
    lines = []
    for line in text.split('\n'):
        lines.append(line)
    # Success
    if i == 1:
        print "{0:>{1}}".format("[done]", 79 - len(lines[-1]))
    # Failure
    elif i == 2:
        print "{0:>{1}}".format("[failed]", 79 - len(lines[-1]))
    # Print the message
    else:
        print text,

'''
################################################################################
PROGRESS BAR

    A progress bar can be useful for a user.  This method was copied (with some
    slight alterations) from Brian Khuu's post here:
        http://stackoverflow.com/questions/3160699/python-progress-bar
################################################################################
'''
def update_progress(progress=1):
    # If we're being quiet, just don't do anything.
    if quiet:
        return
    # Modify this to change the length of the progress bar:
    barLength = 50
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "Error: progress var must be float.\r\n"
    if progress < 0:
        progress = 0
        status = "[failed]\r\n"
    if progress >= 1:
        progress = 1
        status = "  [done]\r\n"
    amount = math.ceil(progress*1000)/10
    block = int(round(barLength*progress))
    text = "\r    [{0}] {1:>5}%{2:>{3}}".format("#"*block + "-"*(barLength-block),
                                                amount,
                                                status,
                                                24 - len(str(amount)))
    sys.stdout.write(text)
    sys.stdout.flush()

'''
################################################################################
QUIET PRINTING

    Simply calls "print" if quiet == False; otherwise it just returns and
    doesn't print.
################################################################################
'''
def qprint(string=""):
    if not quiet:
        print string
        return
    else:
        return

'''
################################################################################
CALL TO MAIN()

    This is our entry point.  It's kind of a big deal.
################################################################################
'''
if __name__ == "__main__":
    main()
