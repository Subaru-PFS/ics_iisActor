import re
import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class LampsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('prepare', '[<hgar>] [<neon>] [<argon>] [<krypton>] [<hydrogen>] [<helium>] [<halogen>]', self.prepare),
            ('go', '[<delay>] [@noWait]', self.go),
            ('stop', '', self.stop),
            ('halt', '', self.halt),
            ('status', '', self.status),
            ('allstat', '', self.allstat),
            ('lamptimes', '', self.lampTimes),
            ('waitForReadySignal', '', self.waitForReadySignal),
            ('pi', '@raw', self.raw),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("lamps_lamps", (1, 1),
                                        keys.Key("hgar", types.Int(), help="HgAr lamp time"),
                                        keys.Key("neon", types.Int(), help="Ne lamp time"),
                                        keys.Key("argon", types.Int(), help="Ar lamp time"),
                                        keys.Key("krypton", types.Int(), help="Kr lamp time"),
                                        keys.Key("hydrogen", types.Int(), help="H lamp time"),
                                        keys.Key("helium", types.Int(), help="He lamp time"),
                                        keys.Key("halogen", types.Int(), help="Quartz lamp time"),
                                        keys.Key("delay", types.Float(), help="time to delay start for"),
                                        keys.Key("moduleNums", types.String(),
                                                 help="spectrograph modules we are connected to. Default='1234'"),
                                        )

        self.lampNames = ('hgar', 'neon', 'argon', 'krypton', 
                          'hydrogen', 'helium', 'halogen')
        self.piLampNames = ('hgar', 'neon', 'argon', 'krypton',
                            'hydrogen', 'helium', 'cont')
        self.statNames = ('HgAr','Ne','Ar','Kr','H','He','Cont')

        self.keyLampNames = {long:short for (long,short) in zip(self.piLampNames, self.statNames)}

        self.request = {}

    @property
    def pi(self):
        return self.actor.controllers['lamps_pi']

    def raw(self, cmd):
        """ Send a raw command to the controller. """

        cmd_txt = cmd.cmd.keywords['raw'].values[0]

        ret = self.pi.lampsCmd(f'raw {cmd_txt}', cmd=cmd)
        cmd.finish('text=%s' % (qstr('returned: %s' % (ret))))

    def prepare(self, cmd):
        """Configure the calibration system lamps for the given exposure times. """

        cmdkeys = cmd.cmd.keywords

        lamps = []
        request = {}
        maxtime = 0
        for name in self.lampNames:
            if name in cmdkeys:
                val = cmdkeys[name].values[0]
                val = int(val)
                if val <= 0:
                    if val < 0:
                        cmd.warn(f'text="negative {name} lamp request ignored"')
                    continue
                if name == 'halogen':
                    name = 'cont'
                lamps.append(f'{name}={val}')
                request[name] = val
                maxtime = max(maxtime, val)
        self.requestTime = maxtime
        self.request = request
        self.genVisitKeys(cmd)

        if len(lamps) == 0:
            cmd.fail('text="at least one lamp must be specified"')
            return

        setupCmd = f'setup {" ".join(lamps)}'
        ret = self.pi.lampsCmd(setupCmd)

        self.genStatusKey(cmd, *self._getStatus(cmd))
        self.reqstat(cmd, doFinish=False)
        self.lampTimes(cmd, doFinish=False)
        cmd.finish()

    def genStatusKey(self, cmd, running, ready, cooling):
        cmd.inform(f'calibState={running},{ready},{cooling}')

    def _getStatus(self, cmd):
        """Get current lamp status."""

        ret = self.pi.lampsCmd('status')
        ok, running, ready, cooling = ret.split()
        if ok != 'OK':
            raise RuntimeError(f'status is bad: {ret}')
        running = int(running)
        ready = int(ready)
        cooling = int(cooling)

        return running, ready, cooling

    def waitForReadySignal(self, cmd, doFinish=True):
        maxtime = 5
        maxWaitForRunningTime = 1
        loopTime = 0.2

        if 'hgcd' in self.request:
            maxtime = 190

        lastRunning = lastReady = lastCooling = None
        startTime = time.time()
        while True:
            running, ready, cooling = self._getStatus(cmd)
            now = time.time()
            if running != lastRunning or ready != lastReady or cooling != lastCooling:
                self.genStatusKey(cmd, running, ready, cooling)
                lastRunning = running
                lastReady = ready
                lastCooling = cooling
            if not running:
                if now - startTime > maxWaitForRunningTime:
                    cmd.fail('text="lamps are not configured"')
                    return
                else:
                    cmd.warn('text="lamps are not configured, but checking again...."')
            if ready:
                break

            now = time.time()
            if now - startTime > maxtime:
                cmd.fail(f'text="lamps did not turn on in {maxtime} seconds.... stopping lamps command"')
                self.request = {}
                self.pi.lampsCmd('stop')
                self.genVisitKeys(cmd)
                return

            time.sleep(loopTime)

        self.allstat(cmd, doFinish=False)
        if doFinish:
            cmd.finish()

    def waitForFinishedSignal(self, cmd):
        maxtime = 15
        startTime = time.time()
        while True:
            running, ready, cooling = self._getStatus(cmd)
            cmd.debug(f'text="running, ready, cooling = {running}, {ready}, {cooling}"')
            if not running:
                return True

            now = time.time()
            if now - startTime > maxtime:
                cmd.fail(f'text="lamps did not turn off in {maxtime} seconds; will try to force things off."')
                self.request = {}
                self.pi.lampsCmd('stop')
                self.genVisitKeys(cmd)
                return False

            time.sleep(0.5)
        self.allstat(cmd, doFinish=False)

    def waitForRunningSignal(self, cmd):
        maxtime = 3
        startTime = time.time()
        while True:
            running, ready, cooling = self._getStatus(cmd)
            cmd.debug(f'text="running, ready, cooling = {running}, {ready}, {cooling}"')
            if running:
                return True

            now = time.time()
            if now - startTime > maxtime:
                cmd.warn(f'text="lamps did not turn on in {maxtime} seconds."')
                return False

            time.sleep(0.5)

    def halt(self, cmd):
        ret = self.pi.lampsCmd('stop')
        self.stop(cmd)

    def stop(self, cmd):
        """Stop any lamp command, and turn off lamps. """

        ret = self.pi.lampsCmd('stop')
        self.request = {}
        self.genStatusKey(cmd, *self._getStatus(cmd))
        self.genVisitKeys(cmd)
        self.reqstat(cmd, doFinish=False)
        self.allstat(cmd, doFinish=False)
        cmd.finish()

    def go(self, cmd):
        """Given the already configured lamps, run the sequence """

        if len(self.request) == 0:
            cmd.fail('text="No lamps requested"')
            return

        cmdKeys = cmd.cmd.keywords
        noWait = 'noWait' in cmdKeys

        self.waitForReadySignal(cmd, doFinish=False)
        cmd.inform('text="lamps ready, turning them on"')
        ret = self.pi.lampsCmd('go')
        self.genVisitKeys(cmd)

        cmd.inform('text="lamps commanded, waiting for status"')        
        self.waitForOnSignal(cmd)
        self.allstat(cmd, doFinish=False)

        waitTime = max(0, self.requestTime-2)

        if noWait:
            cmd.finish(f'text="lamps should be on; please wait {waitTime} to be safe."')
            return
        elif waitTime > 0:
            cmd.inform(f'text="waiting {waitTime} for lamps to go out."')
            time.sleep(waitTime)

        self.allstat(cmd, doFinish=False)
        ok = self.waitForFinishedSignal(cmd)
        self.allstat(cmd, doFinish=False)
        ok = True
        if ok:
            cmd.finish()

    def genVisitKeys(self, cmd):
        """Generate MHS keys based on confguration and status.

        Slightly tricky.

        For the headers, the keys at the end of the exposure will be
        latched. So we generate keys just before the prepare based on
        status: these should all indicate OFF. Then we generate keys
        mostly based on allstat taken imediately after the go command:
        these should match the request, and be valid if we ask fast
        enough.

        We also want to be able to query the current lamp status at any time.
        """
        def lampStateName(val):
            return 'on' if val else 'off'

        mask = [lampStateName(name in self.request) for name in self.piLampNames]
        times = [str(self.request.get(name, 0)) for name in self.piLampNames]

        cmd.inform(f'lampRequestMask={",".join(mask)}')
        cmd.inform(f'lampRequestTimes={",".join(times)}')

    def reqstat(self, cmd, doFinish=True):
        for lampName in self.piLampNames:
            request = self.request.get(lampName, 0.0)
            keyName = self.keyLampNames[lampName]
            state = "on" if request > 0 else "off"
            cmd.inform(f'{keyName}State={state},{request:0.2f}')
        if doFinish:
            cmd.finish()

    def status(self, cmd):
        """Get current lamp status."""

        self.actor.sendVersionKey(cmd)

        cmd.inform(f'modules={self.actor.actorConfig["modules"]}')
        
        self.genStatusKey(cmd, *self._getStatus(cmd))
        self.lampTimes(cmd, doFinish=False)
        cmd.finish()

    def waitForOnSignal(self, cmd, maxWait=5):

        t0 = time.time()
        while True:
            ret = self.pi.lampsCmd('raw tail -1 /tmp/runlog.txt')
            cmd.diag(f'text="received {ret}"')
            ret = ret.strip()
            if ' on 'in ret:
                return
            t1 = time.time()
            if t1-t0 > maxWait:
                return
            time.sleep(0.1)

    def _allstat(self, cmd):
        """Fetch and parse lamp and photodiode outputs.

        Notes
        -----
        Expected output:
           2023-07-19T20:19:22   off off off off off off off on    0.0000 0.0000"
        where the lamp order is: hgar neon argon krypton h he spare cont

        Note that we drop the "spare" lamp here.
        """

        statusDict = {}

        ret = self.pi.lampsCmd('raw tail -1 /tmp/runlog.txt')
        cmd.diag(f'text="received {ret}"')
        ret = ret.strip()

        ts, *parts = re.split('\s+', ret)
        states = parts[:6] + parts[7:8] # Skip the spare lamp
        diodes = [float(p) for p in parts[8:10]]
        cmd.diag(f'text="states={states} diodes={diodes}"')
        for i, n in enumerate(self.statNames):
            statusDict[n] = f'{diodes[0]},{diodes[1]}'
            statusDict[n+"_state"] = states[i]
        return statusDict

    def allstat(self, cmd, doFinish=True):
        statDict = self._allstat(cmd)

        for lamp in self.statNames:
            cmd.inform(f'{lamp}State={statDict[lamp+"_state"]},{statDict[lamp]}')
        self.lampTimes(cmd, doFinish=False)
        if doFinish:
            cmd.finish()

    def lampTimes(self, cmd, doFinish=True):
        """Fetch lamp on and off times."""
        ret = self.pi.lampsCmd('lampTimes')
        lines = ret.split('\n')
        for l in lines:
            cmd.inform(l)
        if doFinish:
            cmd.finish()

