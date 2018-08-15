#!/usr/bin/env python
#    Terminator - multiple gnome terminals in one window
#    Copyright (C) 2006-2010  cmsj@tenshu.net
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 2 only.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
#    USA

"""Terminator by Chris Jones <cmsj@tenshu.net>"""

import sys
import os
import psutil
import pwd
try:
    ORIGCWD = os.getcwd()
except OSError:
    ORIGCWD = os.path.expanduser("~")

# Check we have simple basics like Gtk+ and a valid $DISPLAY
try:
    import gi
    gi.require_version('Gtk', '3.0')
    # pylint: disable-msg=W0611
    from gi.repository import Gtk, Gdk

    if Gdk.Display.get_default() is None:
        print('You need to run terminator in an X environment. '
              'Make sure $DISPLAY is properly set')

        sys.exit(1)

except ImportError:
    print('ERROR You need to install the python bindings for '
          'gobject, gtk and pango to run Terminator.')

    from textwrap import dedent
    print(dedent(
        '''
        INSTALL INSTRUCTIONS
        ====================


        NOTE: Installing GTK3.0 is not well defined at the moment

        WIP::
            sudo apt install python-gi
            sudo apt install python3-gi
            pip install pgi

            conda install -c pkgw/label/superseded gtk3
            conda install -c pkgw-forge gtk3
            conda install gtk3

            python -c "import gi"

        pip install -r requirements.txt -U
        python setup.py install --record=install-files.txt --prefix=$HOME/.local

        # OLD WAY
        python -m terminator
        ./terminator
        # NEW WAY (broken)

        Uninstall
        =========

        python setup.py uninstall --manifest=install-files.txt



        '''))
    raise
    sys.exit(1)

from . import terminatorlib
from .terminatorlib import optionparse
from .terminatorlib.terminator import Terminator
from .terminatorlib.factory import Factory
from .terminatorlib.version import APP_NAME, APP_VERSION
from .terminatorlib.util import dbg, err
from .terminatorlib.layoutlauncher import LayoutLauncher

if __name__ == '__main__':
    # Workaround for IBus intefering with broadcast when using dead keys
    # Environment also needs IBUS_DISABLE_SNOOPER=1, or double chars appear
    # in the receivers.
    username = pwd.getpwuid(os.getuid()).pw_name
    ibus_running = [p for p in psutil.process_iter(
    ) if p.name == 'ibus-daemon' and p.username == username]
    ibus_running = len(ibus_running) > 0
    if ibus_running:
        os.environ['IBUS_DISABLE_SNOOPER'] = '1'

    dbus_service = None

    dbg("%s starting up, version %s" % (APP_NAME, APP_VERSION))

    OPTIONS = optionparse.parse_options()

    if OPTIONS.select:
        # launch gui, return selection
        LAYOUTLAUNCHER = LayoutLauncher()
    else:
        # Attempt to import our dbus server. If one exists already we will just
        # connect to that and ask for a new window. If not, we will create one and
        # continue. Failure to import dbus, or the global config option "dbus"
        # being False will cause us to continue without the dbus server and open a
        # window.
        try:
            if OPTIONS.nodbus:
                dbg('dbus disabled by command line')
                raise ImportError
            from terminatorlib import ipc
            import dbus
            try:
                dbus_service = ipc.DBusService()
            except ipc.DBusException:
                dbg('Unable to become master process, operating via DBus')
                # get rid of the None and True types so dbus can handle them (empty
                # and 'True' strings are used instead), also arrays are joined
                # (the -x argument for example)
                if OPTIONS.working_directory is None:
                    OPTIONS.working_directory = ORIGCWD
                optionslist = {}
                for opt, val in list(OPTIONS.__dict__.items()):
                    if isinstance(val, list):
                        val = ' '.join(val)
                    if val is True:
                        val = 'True'
                    optionslist[opt] = val and '%s' % val or ''
                optionslist = dbus.Dictionary(optionslist, signature='ss')
                if OPTIONS.new_tab:
                    dbg('Requesting a new tab')
                    ipc.new_tab_cmdline(optionslist)
                else:
                    dbg('Requesting a new window')
                    ipc.new_window_cmdline(optionslist)
                sys.exit()
        except ImportError:
            dbg('dbus not imported')
            pass

        MAKER = Factory()
        TERMINATOR = Terminator()
        TERMINATOR.set_origcwd(ORIGCWD)
        TERMINATOR.set_dbus_data(dbus_service)
        TERMINATOR.reconfigure()
        TERMINATOR.ibus_running = ibus_running

        try:
            dbg('Creating a terminal with layout: %s' % OPTIONS.layout)
            TERMINATOR.create_layout(OPTIONS.layout)
        except (KeyError, ValueError) as ex:
            err('layout creation failed, creating a window ("%s")' % ex)
            TERMINATOR.new_window()
        TERMINATOR.layout_done()

    if OPTIONS.debug >= 2:
        import terminatorlib.debugserver as debugserver
        # pylint: disable-msg=W0611
        import threading  # NOQA

        Gdk.threads_init()
        (DEBUGTHREAD, DEBUGSVR) = debugserver.spawn(locals())
        TERMINATOR.debug_address = DEBUGSVR.server_address

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
