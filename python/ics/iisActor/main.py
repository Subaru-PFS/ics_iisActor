#!/usr/bin/env python3

import logging
import actorcore.ICC

class OurActor(actorcore.ICC.ICC):
    def __init__(self, name,
                 productName=None,
                 modelNames=('gen2'),
                 debugLevel=30):

        """ Setup an Actor instance. See help for actorcore.Actor for details. """
        
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name,
                                   productName=productName,
                                   modelNames=modelNames)

        self.everConnected = False

        self.monitors = dict()

    def reloadConfiguration(self, cmd):
        cmd.inform('sections=%08x,%r' % (id(self.config),
                                         self.config))

    def connectionMade(self):
        if self.everConnected is False:
            logging.info("Attaching all controllers...")
            self.allControllers = self.actorConfig['controllers']['starting']
            self.attachAllControllers()
            self.everConnected = True

            _needModels = [self.name]
            self.logger.info(f'adding models: {_needModels}')
            self.addModels(_needModels)
            self.logger.info(f'added models: {self.models.keys()}')

        # At this

#
# To work
def main():
    theActor = OurActor(name='iis',
                        productName='iisActor')
    theActor.run()

if __name__ == '__main__':
    main()
