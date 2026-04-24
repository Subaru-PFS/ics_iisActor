#!/usr/bin/env python3

import argparse
import logging
import os
import socketserver
import subprocess
import tempfile
import threading
import time

logging.basicConfig(format="%(asctime)s.%(msecs)03d %(levelno)s %(name)-10s %(message)s",
                    filename='/tmp/cmds.txt', datefmt="%Y-%m-%dT%H:%M:%S")
logger = logging.getLogger('caliblamp')
logger.setLevel(logging.DEBUG)

class CaliblampState:
    RUNNING_FILE = "/tmp/calibrunning"
    READY_FILE = "/tmp/calibready"
    COOLING_FILE = "/tmp/calibcooling"

    lampNames = {'hgar', 'neon', 'argon', 'krypton', 'hydrogen', 'helium', 'cont'}

    def __init__(self):
        """
        Track and control the calibration lamp, mostly via files in /tmp.

        Newer versions of this scheme (SuNSS, say) only use /tmp
        files. Might switch. In the meanwhile, need to call shell
        routines. Slightly tricky.
        
        calibrunning is created when lamps() is called and deleted
        when it finishes, so when it exists the system is active. It
        contains one line with the PID of the lamps() process, which
        runs in a subshell. It is deleted at the end of the lamps
        ignition sequence.

        calibready is created when the lamps have been warmed up and
        are ready to run. It is *deleted* when the lamps ign ition
        sequence has been started.

        calibcooling exists after the lamps have been run, and the
        cooling fans are running.

        calibtesting exists when in testing mode. Monitor is off, mode
        turns itself and all lamps off and file is deleted after 1 hour.
        """
        pass

    def cmd(self, cmdStr):
        """Call one of the caliblamps primitive shell functions or commands. """
        res = subprocess.run(["/bin/bash", "-c", "source /usr/local/bin/caliblamps && %s" % (cmdStr)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = res.stdout.decode('latin-1')
        logger.info('command: %s output: %s', cmdStr, output)
        return output
        
    def isRunning(self):
        return str(int(os.path.exists(self.RUNNING_FILE)))

    def isReady(self):
        return str(int(os.path.exists(self.READY_FILE)))

    def isCooling(self):
        return str(int(os.path.exists(self.COOLING_FILE)))

    def status(self):
        return 'OK %s %s %s' % (self.isRunning(), self.isReady(), self.isCooling())

    def stop(self):
        """ Stop the lamps systems. """

        self.cmd('stop')
        return self.status()

    def go(self, maxTime=30):
        """ Light the configured lamp sequence. """

        self.cmd('go')
        return self.status()

    def setup(self, lamps):
        """ Configure the lamp sequence. """

        self.cmd('lamps %s ' % (lamps))
        return self.status()

    def allstat(self):
        ret = self.cmd('allstat')
        return ret

    def runstat(self):
        ret = self.cmd('tail -1 /tmp/runlog.txt')
        return ret

    def lampTimes(self):
        """Return the off and on times for all lamps."""
        ret = self.cmd('lamptimes')
        return ret
    
class CaliblampRequestHandler(socketserver.BaseRequestHandler):
    def setup(self):
        self.caliblampState = self.server.caliblampState

    def setupCmd(self, rawCmd):
        """Parse and execute a lamps setup command"""
        cmdParts = []

        for lampPart in rawCmd:
            try:
                name, timeStr = lampPart.split('=')
            except ValueError:
                return 'ERROR : lamp word not name=time: %s' % (lampPart)

            if name not in self.caliblampState.lampNames:
                return 'ERROR : unknown lamp name: %s' % (name)

            try:
                timeVal = int(timeStr)
            except ValueError:
                return 'ERROR : lamp time not an int: %s' % (timeStr)

            cmdParts.append('%s %s' % (name, timeVal))

        cmdStr = ' '.join(cmdParts)
        return self.caliblampState.setup(cmdStr)

    def handle(self):
        rawCmd = str(self.request.recv(1024), 'latin-1')
        cmd = rawCmd.split()
        logger.info("cmd: %s", cmd)

        cmdName = cmd[0]
        if cmdName == 'setup':
            ret = self.setupCmd(cmd[1:])
        elif cmdName == 'go':
            ret = self.caliblampState.go()
        elif cmdName == 'stop':
            ret = self.caliblampState.stop()
        elif cmdName == 'status':
            ret = self.caliblampState.status()
        elif cmdName == 'allstat':
            ret = self.caliblampState.allstat()
        elif cmdName == 'runstat':
            ret = self.caliblampState.runstat()
        elif cmdName == 'lampTimes':
            ret = self.caliblampState.lampTimes()
        elif cmdName == 'raw':
            _, cmdStr = rawCmd.split(None, 1)
            logger.info("raw: %s", cmdStr)
            ret = self.caliblampState.cmd(cmdStr)
        else:
            ret = 'ERROR : unknown command'

        logger.info("ret: %s", ret)
        response = ret + '\0'
        self.request.sendall(response.encode('latin-1'))

class CaliblampServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self, *kl, caliblampState=None, **kv):
        self.caliblampState = caliblampState
        super().__init__(*kl, **kv)
        self.allow_reuse_address = True
        self.name = 'caliblamp'

def run():
    state = CaliblampState()
    ip, port = '', 7000
    server = CaliblampServer((ip, port), CaliblampRequestHandler, caliblampState=state)
    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=server.serve_forever)

    # Exit the server thread when our thread terminates
    server_thread.daemon = True
    logger.info("Server loop starting in thread: %s", server_thread.name)
    server_thread.start()
    server_thread.join()
    logger.info("Server loop done in thread:", server_thread.name)

def main(argv=None):
    if isinstance(argv, str):
        import shlex
        argv = shlex.split(argv)

    parser = argparse.ArgumentParser()
    # args = parser.parse(argv)

    run()

if __name__ == "__main__":
    main()
