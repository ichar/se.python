# -*- coding: utf-8 -*-

#import os
#import sys
import time

from PyQt4 import QtCore

#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config, ERRORLOG as errorlog, IsDebug, IsDeepDebug
from ..services import Kad, SearchData

mutex = QtCore.QMutex()

_default_progress = (0, 100, '')


class TestService(object):

    def __init__(self, consumer, **kw):
        self.consumer = consumer

        # Mandatory progress attributes
        self._progress = None
        self._stage = 0
        self._ready = False

        self._timeout = kw.get('timeout') or 3.0

        # Optional step attributes
        self._count = 0
        self._max = 10

    def _init_state(self, **kw):
        #
        # Set initial progress state
        #
        self._progress = { \
            'top'    : list(_default_progress).copy(),
            'bottom' : list(_default_progress).copy(),
            'found'  : 0,
            'ready'  : 0
        }

        self._progress['bottom'][1] = self._max
        self._progress['top'][2] = 'Инициализация сервиса'
        self._ready = False

    def getState(self):
        return self._progress

    def init(self):
        #
        # Init next (regular) step
        #
        self._progress['bottom'] = list(_default_progress).copy()
        self._progress['bottom'][1] = self._max

        self._ready = True

    def isReady(self):
        return self._ready

    def stage_1(self):
        #
        # Run stage 1 (top progress)
        #
        time.sleep(0.1)
        self._progress['bottom'][0] = 0

    def stage_2(self):
        #
        # Run stage 2 (bottom progress)
        #
        time.sleep(0.1)

    def run(self):
        #
        # Main process controller
        #
        if self._stage == 0:
            if self._progress['top'][0] < self._progress['top'][1]:
                self._progress['top'][2] = '%s [%s] ...' % ("Чтение данных", str(self._progress['top'][0]+1))
                self.consumer.progress()

                self.stage_1()

                #self._progress['top'][2] = ''
                #self._ready = False
                self._count = 0
                self._stage = 1
            else:
                self.consumer.finish()
                self.consumer = None
                self._stage = 0
        else:
            if self._count < self._max:
                if self.consumer.getStop():
                    return

                self._progress['bottom'][2] = '%s [%s] ...' % ("Данные", str(self._progress['bottom'][0]+1))
                self.consumer.progress()

                self.stage_2()

                self._progress['bottom'][0] += 1
                #self._progress['bottom'][2] = ''
                self._count += 1
            else:
                self._progress['top'][0] += 1
                self._stage = 0


class ModXThread(QtCore.QThread):

    def __init__(self, consumer):
        super(ModXThread, self).__init__()

        self.consumer = consumer
        self.supplier = None

        self._progress = None
        self._ready = False
        self._stop = False
        self._error = None
        self._finished = False
 
        self._options = {}
        self._items = []

    def __del__(self):
        if IsDebug:
            self.logger.out('destroy')

        self.wait()

    def _init_state(self, service, logger=None, **kw):
        self.logger = logger

        if service == 'TestService':
            self.supplier = TestService(self, **kw)
        elif service == 'Kad':
            self.supplier = Kad(self, **kw)
        else:
            self.supplier = SearchData(self, **kw)

        self._items = [x for x in kw.get('items', [])]
        self._options = kw.get('options') or {}

        self.supplier._init_state(logger=self.logger)

    def _set_state(self, progress, **kw):
        #
        # progress : dict {'top':[<count>, <max>, <title>], 'bottom':[<count>, <max>, <title>]}
        #
        self._progress = progress

    def options(self, mode='get', values=None):
        if mode == 'set':
            if values is not None:
                self._options = values or {}
            if IsDebug:
                self.logger.out('options: %s' % self._options)
        else:
            mutex.lock()
            values = self._options
            mutex.unlock()
            return values

    def items(self, mode='get', values=None):
        if mode == 'set':
            if values:
                for item in values:
                    if item not in self._items:
                        self._items.append(item)
            if IsDebug:
                self.logger.out('items: %s %s' % (len(self._items), self._items))
        elif mode == 'len':
            mutex.lock()
            value = len(self._items)
            mutex.unlock()
            return value
        else:
            mutex.lock()
            values = self._items
            mutex.unlock()
            return values

    def push(self, item):
        mutex.lock()
        self._items.append(item)
        mutex.unlock()

    def pop(self):
        mutex.lock()
        item = self._items.pop(0)
        mutex.unlock()
        return item
 
    def getStop(self):
        return self._stop

    def set_error(self, code, msg=None):
        self._error = (code, msg,)
        #self.emit(QtCore.SIGNAL('error'), self._error, msg)

    def init(self, **kw):
        # Get initial state
        self._set_state(progress=self.supplier.getState())
        self.emit(QtCore.SIGNAL('init'), self._progress)

        self.supplier.init()

        self._stop = False
        self._ready = True

        if IsDebug:
            self.logger.out('init')

    def run(self):
        self._stop = False

        # Check whether consumer's was started
        if not self.consumer.getStarted():
            return

        if IsDebug:
            self.logger.out('start')

        while not self._stop:
            # Check service is ready
            if not (self._ready and self.supplier.isReady()):
                self.init()

            # Check an error
            if self._error:
                self.emit(QtCore.SIGNAL('error'), self._error[0], self._error[1])
                self._stop = True

            else:
                # Run stage
                self.supplier.run()

                # Show consumer's progress
                self.progress()

        if self._finished:
            time.sleep(1.0)
            self.emit(QtCore.SIGNAL('service-finished'))

    def close(self):
        #self.terminate()
        if IsDebug:
            self.logger.out('close')
        #self._stop = True

    def progress(self):
        # Get current state
        self._set_state(progress=self.supplier.getState())
        self.emit(QtCore.SIGNAL('progress'), self._progress)

    def stop(self):
        if self.consumer.getStarted():
            return

        if IsDebug:
            self.logger.out('stop')

        self._stop = True
        self._error = None
        #self._ready = False

    def finish(self):
        self._stop = True
        self._finished = True
        self.emit(QtCore.SIGNAL('finish'))
