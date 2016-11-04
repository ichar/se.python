#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import datetime
import subprocess
import webbrowser

absbasedir = os.getcwd() #os.path.abspath(os.path.dirname(__file__))

#sys.path.append(basedir)
#sys.path.append(os.path.join(basedir, 'app'))
#sys.path.append(os.path.join(basedir, 'app', 'connectors'))
#sys.path.append(os.path.join(basedir, 'app', 'engines'))
#sys.path.append(os.path.join(basedir, 'app', 'ui'))

# This is only needed for Python v2 but is harmless for Python v3.
import sip
sip.setapi('QVariant', 2)

from PyQt4 import QtCore, QtGui

from config import (
     Config, ERRORLOG as errorlog, basedir, IsDebug, IsDeepDebug)

from app.ui.ui_dialog_settings import Ui_DialogSettings
from app.ui.ui_main import Ui_MainWindow

from app.connectors.mod_x import ModXThread, mutex
from app.dbase import getDBPageSize, getDBFilterColumn, getDBStatus, DBConnector
from app.logger import Logger
from app.utils import make_html

IsSelfTest = 0

_service_messages = { \
    'init'     : 'Инициализация...',
    'error'    : 'Ошибка...',
    'continue' : 'Продолжить',
}

_default_options = { \
    'modes' : { \
        'email'   : 1,
        'phone'   : 1,
        'address' : 1,
        'manager' : 1,
    },
    'options' : { \
        'top'     : Config['DEFAULT'].getboolean('default_top') and 1 or 0,
    },
    'engines' : { \
        'ask'     : 1,
        'bing'    : 1,
        'google'  : 1,
        'mail'    : 1,
        'rambler' : 1,
        'yahoo'   : 1,
        'yandex'  : 1,
    },
}

_default_status_icons = ( \
    QtGui.QStyle.SP_MessageBoxInformation,
    QtGui.QStyle.SP_MessageBoxWarning,
    QtGui.QStyle.SP_CommandLink,
    QtGui.QStyle.SP_DialogApplyButton, #SP_DialogOkButton #SP_FileDialogEnd
    QtGui.QStyle.SP_MessageBoxCritical,
)

_default_status_backgrounds = ( \
    '#FFFFFF',
    '#FFFECE', # '#FDDFE4', # '#FCC8D0', 
    '#E4F0E0',
    '#E4E4E4',
    '#FFC6C6',
)

_default_page_size = 1
_default_filter_column = 0
_default_date_format = ('yyyy-MM-dd', '%Y-%m-%d')

_const_width_symbol = Config['DEFAULT'].getint('const_width_symbol')
_default_threshold = Config['DEFAULT'].getint('default_threshold')
_default_count = Config['DEFAULT'].getint('default_count')
_default_date_from_delta = Config['DEFAULT'].getint('default_date_from_delta')
_default_font_family = Config['DEFAULT'].get('default_font_family')
_default_font_size = Config['DEFAULT'].getint('default_font_size')
_default_font_color = Config['DEFAULT'].get('default_font_color')
_default_controls_font_size = Config['DEFAULT'].get('default_controls_font_size')

_default_clock = {'wait':0, 'start':None, 'idle':None}


def _get_items(value):
    return ';\n'.join(value)

class ExtWindow(object):

    def setExtFont(self, control, family=_default_font_family, size=_default_font_size):
        font = QtGui.QFont()
        font.setFamily(family)
        font.setPixelSize(size)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        control.setFont(font)

    def setTextEditDecoration(self, control, color=_default_font_color, **kw):
        self.setExtFont(control, **kw)

        if color:
            x = color.split(':')
            if len(x) >= 3:
                color = "color: rgb(%s, %s, %s);" % (x[0], x[1], x[2])
                control.setStyleSheet(color)

    def setListItemDecoration(self, control, color=_default_font_color, **kw):
        self.setExtFont(control, **kw)

        if color:
            x = color.split(':')
            if len(x) >= 3:
                color = QtGui.QColor(int(x[0]), int(x[1]), int(x[2]))
                control.setForeground(color)


class AppMainWindow(QtGui.QMainWindow, Ui_MainWindow, ExtWindow):

    def __init__(self, parent=None):
        super(AppMainWindow, self).__init__(parent)

        self.setupUi(self)

        self.dialogSettings = None
        self.modXThread = None

        self.modX_top_count = 0
        self.modX_bottom_count = 0
        self.modX_ready = False
        self.timer = None

        self._total = 0
        self._found = 0
        self._ready = 0
        self._sent = 0

        self._clock = None
        self._selected_id = None
        self._ids = None
        self._selected_email = None
        self._selected_phone = None

        self._page = 0
        self._page_size = 0
        self._page_count = 0
        self._filter_column = 0
        self._filter_text = ''
        self._selected_items = 0

    def _init_state(self, styleName, logger=None):
        self.logger = logger

        self._current_service = -1

        QtGui.QApplication.setStyle(QtGui.QStyleFactory.create(styleName))
        QtGui.QApplication.setPalette(QtGui.QApplication.style().standardPalette())

        self.gridLayoutProgress.setContentsMargins(-1, -1, 261, -1)
        self.setCurrentDateFrom()

        size = _default_controls_font_size.split(':')
        self.setTextEditDecoration(self.textFromName, size=int(size[0]))
        self.setTextEditDecoration(self.textToName, size=int(size[1]))
        self.setTextEditDecoration(self.textToAddress, size=int(size[2]))
        self.setTextEditDecoration(self.textManager, size=int(size[3]))

        self.hide_form()

        self.dialogSettings = AppDialogSettings()
        self.dialogSettings._init_state(_default_options)

        self.connect(self.dialogSettings, QtCore.SIGNAL("settings"), self.updateSettings)

        if IsDebug:
            self.logger.out('init_state')

        self.initClock(1)

        if IsSelfTest:
            self.services = ['TestService']
        else:
            self.services = ['Kad', 'SearchData']

        #self.buttonSendMail.clicked.connect(self.on_buttonSendMail_clicked)

        self.db = DBConnector()

        self.progressBarTop.setMaximum(0)
        self.progressBarTop.setValue(0)

        self.progressBarBottom.setMaximum(0)
        self.progressBarBottom.setValue(0)

        self.init_statusbar()

        self.refresh()

    def _init_service(self):
        if self._current_service >= len(self.services):
            self._current_service = -1
        if self._current_service < 0:
            self._current_service = 0
            self.initClock(1)
        if self.dialogSettings.isLoadingDisabled() and len(self.services) > 1:
            self._current_service = 1

        if IsDebug:
            self.logger.out('init_service')

        service = self.services[self._current_service]
        self._current_service += 1

        self.modXThread = ModXThread(self)

        self.labelTopProgress.setText('') #_service_messages['init']
        self.labelBottomProgress.setText('')

        self.disconnect(self.modXThread, QtCore.SIGNAL("error"), self.modX_error)
        self.disconnect(self.modXThread, QtCore.SIGNAL("init"), self.modX_init)
        self.disconnect(self.modXThread, QtCore.SIGNAL("progress"), self.modX_progress)
        self.disconnect(self.modXThread, QtCore.SIGNAL("finish"), self.modX_finish)
        self.disconnect(self.modXThread, QtCore.SIGNAL("service-finished"), self.modX_finished)

        self.connect(self.modXThread, QtCore.SIGNAL("error"), self.modX_error)
        self.connect(self.modXThread, QtCore.SIGNAL("init"), self.modX_init)
        self.connect(self.modXThread, QtCore.SIGNAL("progress"), self.modX_progress)
        self.connect(self.modXThread, QtCore.SIGNAL("finish"), self.modX_finish)
        self.connect(self.modXThread, QtCore.SIGNAL("service-finished"), self.modX_finished)

        self.modXThread._init_state(service, logger=logger, date_from=self.getDateFrom())

        self.updateSettings()
        self.updateItems()

        self.reset()

    def getStarted(self):
        return self._started

    def getDateFrom(self, date_only=None):
        return '%s%s' % (self.boxDateFrom.date().toString(_default_date_format[0]), not date_only and 'T00:00:00' or '')

    def setCurrentDateFrom(self):
        value = (datetime.datetime.now() - datetime.timedelta(_default_date_from_delta)).strftime(_default_date_format[1])
        self.boxDateFrom.setDate(QtCore.QDate.fromString(value, _default_date_format[0]))

    def showMessage(self, title, text, detailed_text=None, width=None):
        m = QtGui.QMessageBox()
        m.setWindowTitle(title)
        m.setIcon(QtGui.QMessageBox.Information)
        m.setText(text)
        if detailed_text:
            m.setDetailedText(detailed_text)
        if width:
            #m.setSizeGripEnabled(True)
            m.setMinimumWidth(width)
            #m.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        m.exec_()

    def setTextValue(self, control, value):
        if not value:
            return
        x = value
        w = control.width()
        if len(x) * _const_width_symbol > w:
            l = int(w/_const_width_symbol)-3
            x = '%s...' % x[:l]
        control.setText(x)

    def show_form(self, mode):
        if 'top' in mode:
            self.progressBarTop.show()
            
        if 'bottom' in mode:
            self.progressBarBottom.show()

    def hide_form(self):
        self.progressBarTop.hide()
        self.progressBarBottom.hide()

        self.labelTopProgress.setText('')
        self.labelBottomProgress.setText('')

    def showCounts(self, refresh=None):
        self.getCurrentState(refresh)

        self.countTotal.setText(str(self._total))
        self.countFound.setText(str(self._found))
        self.countReady.setText(str(self._ready))
        self.countSent.setText(str(self._sent))

    def showPageNumber(self):
        self.statusPageLabel.setText("Стр: %s из %s" % (self._page, self._page_count))

    def showSelectedMessage(self):
        self.statusMessage.setText("Выделено записей: %s" % self._selected_items)

    def connectTableEvents(self):
        self.boxDateFrom.dateChanged.connect(self.changeDateFrom)
        self.boxPageSize.currentIndexChanged.connect(self.changePageSize)
        self.boxFilterColumn.currentIndexChanged.connect(self.changeFilterColumn)
        self.lineFilterText.returnPressed.connect(self.changeFilterText)
        self.boxStatus.currentIndexChanged.connect(self.changeStatus)
        self.tableResults.itemChanged.connect(self.selectTableItem)
        self.tableResults.itemSelectionChanged.connect(self.changeSelectionTableItem)

    def disconnectTableEvents(self):
        try:
            self.boxDateFrom.dateChanged.disconnect(self.changeDateFrom)
            self.boxPageSize.currentIndexChanged.disconnect(self.changePageSize)
            self.boxFilterColumn.currentIndexChanged.disconnect(self.changeFilterColumn)
            self.lineFilterText.returnPressed.disconnect(self.changeFilterText)
            self.boxStatus.currentIndexChanged.disconnect(self.changeStatus)
            self.tableResults.itemChanged.disconnect(self.selectTableItem)
            self.tableResults.itemSelectionChanged.disconnect(self.changeSelectionTableItem)
        except:
            pass

    def init_statusbar(self):
        self.statusPageLabel = QtGui.QLabel()
        self.statusPageLabel.setMaximumWidth(100)
        self.statusPageLabel.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)
        self.statusBar.addWidget(self.statusPageLabel, 1)

        self.statusMessage = QtGui.QLabel()
        self.statusMessage.setMaximumWidth(150)
        self.statusBar.addWidget(self.statusMessage, 1)

    def init_form(self, no_query=None):
        self.reset(no_query)

        self.textFromName.setText('')
        self.textToName.setText('')
        self.textToAddress.setText('')
        self.textManager.setText('')

        self.viewEmails.clear()
        self.viewPhones.clear()

    # -------------------
    #   Events Handlers
    # -------------------

    def exit(self):
        try:
            self.dialogSettings.close()
            self.close()
        except:
            pass

    def closeEvent(self, e):
        self.modX_stop()

    def updateSettings(self):
        if self.modXThread is None:
            return

        options = self.dialogSettings.getState()
        mutex.lock()
        self.modXThread.options('set', options)
        mutex.unlock()

    def updateItems(self):
        if self.modXThread is None:
            return

        items = []
        for row in range(self.tableResults.rowCount()):
            item0 = self.tableResults.item(row, 0)
            if item0.checkState() == QtCore.Qt.Checked:
                items.append(item0.data(QtCore.Qt.UserRole)) #self.get_ids(['pid'])

        mutex.lock()
        self.modXThread.items('set', items)
        mutex.unlock()

    def initClock(self, restart=0):
        if restart or self._clock is None:
            self._clock = _default_clock.copy()
        self.lcdClock.display('00:00:00')

    def startClock(self):
        self.initClock()

        if not self._clock['start']:
            self._clock['start'] = datetime.datetime.now()
        if not self._clock['idle'] is None:
            self._clock['wait'] += (datetime.datetime.now() - self._clock['idle']).seconds
            self._clock['idle'] = None

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.showTime)
        self.timer.start(1000)

        self.showTime()

    def stopClock(self, restart=0):
        if not self.timer:
            return
        self.timer.timeout.disconnect(self.showTime)
        self.timer = None
            
        if not restart:
            self._clock['idle'] = datetime.datetime.now()
        else:
            self.initClock(1)

    def showTime(self):
        if self.timer is None or self._clock is None or self._clock['start'] is None:
            return

        t = datetime.datetime.now() - self._clock['start']
        x = t.seconds - self._clock['wait']
        h = int((x) / 3600)
        m = int((x-(h*3600)) / 60)
        s = int((x-(h*3600)-(m*60)))
        p = ':' #(x % 2) != 0 and ':' or ' '
        text = '%02d%s%02d%s%02d' % (h, p, m, p, s)

        self.lcdClock.display(text)

    def setFormState(self):
        if self._selected_id is not None:
            ids = self.get_ids(self._selected_id)
            save = False
            send = True
            output = not self.db.isOutputEnabled('output', id=ids['rid']) and True or False
            doc = not self.db.isOutputEnabled('doc', id=ids['rid']) and True or False
            status = ids['status']
        else:
            save = send = output = doc = True
            status = 0

        self.buttonSave.setDisabled(save)
        self.buttonNewEmail.setDisabled(save)
        self.buttonEditEmail.setDisabled(True)
        self.buttonRemoveEmail.setDisabled(True)
        self.buttonNewPhone.setDisabled(save)
        self.buttonEditPhone.setDisabled(True)
        self.buttonRemovePhone.setDisabled(True)

        self.buttonOpenOutput.setDisabled(output)
        self.buttonOpenDoc.setDisabled(doc)
        self.buttonSendMail.setDisabled(send)

        self.boxStatus.setCurrentIndex(status)

    def on_buttonSettings_clicked(self):
        self.dialogSettings.show()

    def on_buttonSendMail_clicked(self):
        reply = QtGui.QMessageBox.question(self, "QMessageBox.question()", 'Do you want to send mail?',
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel)

    def buttonStartReleased(self):
        if self._started:
            return

        self.modX_start()

    def buttonStopReleased(self):
        if not self._started:
            return

        self.modX_stop()

    def openOutput(self):
        ids = self.get_ids(self._selected_id)

        output = os.path.join(absbasedir, self.db.getOutput('output', ids['rid']))

        #p = subprocess.Popen(["notepad.exe", output])
        html = output.replace('.txt', '.html')
        if not os.path.exists(html):
            make_html(output)
        url = 'file://' + html.replace('\\', '/')
        webbrowser.open(url, new=1)

    def openDoc(self):
        pass

    # ---------------------------
    #   Database Event Handlers
    # ---------------------------

    def changeDateFrom(self):
        if IsDebug:
            self.logger.out('changeDateFrom')

        self.firstPage()
        self.showCounts()

    def changePageSize(self):
        values = getDBPageSize()
        n = self.boxPageSize.currentIndex()
        self._page_size = values[n][0]
        self.firstPage()

    def changeFilterColumn(self):
        self._filter_column = self.boxFilterColumn.currentIndex()

    def changeFilterText(self):
        self.search()

    def changeStatus(self):
        if self._show or not self._selected_id or self.boxStatus.currentIndex() < 0:
            return
        ids = self.get_ids(self._selected_id)
        if ids['status'] == self.boxStatus.currentIndex():
            return

        self.db.setStatus(self._selected_id, self.boxStatus.currentIndex())

        self.refreshRowItems()

        self.showCounts(refresh=True)

    def changeSelectionTableItem(self):
        current_row = self.tableResults.currentRow()
        self.selectTableRow(current_row)

    def clickTableItem(self, item):
        current_row = item.row()
        self.selectTableRow(current_row)

    def selectTableItem(self, item):
        #
        # Item checked (put it in the stack)
        #
        if self._show:
            return

        selected_id = item.data(QtCore.Qt.UserRole)

        if item.flags() & QtCore.Qt.ItemIsUserCheckable:
            if item.checkState() == QtCore.Qt.Checked:
                self._selected_items += 1
            else:
                self._selected_items -= 1

            self.showSelectedMessage()

        # TODO !!!

    def selectTableRow(self, current_row):
        #
        # Row selected
        #
        self.set_selected_id(current_row)
        self.showDataItems()

    def unselect(self):
        self._show = True

        self._selected_items = 0

        for row in range(self.tableResults.rowCount()):
            item0 = self.tableResults.item(row, 0)

            if not self._unselected:
                check = QtCore.Qt.Unchecked
            else:
                selected_id = item0.data(QtCore.Qt.UserRole)
                check = self.db.shouldItemBeSelected(selected_id, check_status=True) and QtCore.Qt.Checked or QtCore.Qt.Unchecked

            item0.setCheckState(check)

            if check:
                self._selected_items += 1

        self._unselected = not self._unselected and True or False

        self._show = False

        self.showSelectedMessage()

    def refresh(self):
        if IsDebug:
            self.logger.out('refresh')

        self.reset()

        self.setupDBWidgets()
        self.setFormState()

    def reset(self, no_query=None):
        if IsDebug:
            self.logger.out('reset')

        self._selected_id = None
        self._ids = None
        self._started = False
        self._show = False
        self._unselected = None
        self._selected_email = None
        self._selected_phone = None

        if no_query is None:
            self._page = 0
            self._page_size = 0
            self._page_count = 0
            self._filter_column = 0
            self._filter_text = ''

        self.lineFilterText.setText(self._filter_text)

        self._selected_items = 0

    def save(self):
        name = self.textToName.toPlainText()
        address = self.textToAddress.toPlainText()
        manager = self.textManager.toPlainText()

        done = self.db.register('respondent', (name, address, manager), id=self._selected_id)
        if not done:
            return

        self.showMessage("Информация в БД", 'Ответчик. Изменения сохранены.', 
            detailed_text='Наименование:\n%s\nАдрес:\n%s\nФИО:\n%s' % (name, address, manager),
            width=300)

        self.refreshRowItems()

    def firstPage(self):
        self._page = 1
        self.setupDBTable()

    def prevPage(self):
        if self._page == 1:
            return
        self._page -= 1
        self.setupDBTable()

    def nextPage(self):
        if self._page == self._page_count:
            return
        self._page += 1
        self.setupDBTable()

    def lastPage(self):
        self._page = self._page_count
        self.setupDBTable()

    def search(self):
        self._filter_text = self.lineFilterText.text()

        self.firstPage()
        self.showCounts()

    def removeCase(self):
        if not self._selected_id:
            return

        reply = QtGui.QMessageBox.question(self, 'Информация Базы Данных', 
            'Вы действительно собираетесь удалить выделенную запись (Дело) из базы данных?',
            QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel)

        if reply == QtGui.QMessageBox.Yes:
            ids = self.get_ids(self._selected_id)

            if self.db.removeCaseById(ids['cid']):
                self.refresh()

    # ---------------------
    #   Database Controls
    # ---------------------

    def get_ids(self, id):
        if not (self._ids and self._ids[0] == id):
            self._ids = (id, self.db.get_ids(id),)
        return self._ids[1]

    def set_selected_id(self, current_row):
        item0 = self.tableResults.item(current_row, 0)
        self._selected_id = item0.data(QtCore.Qt.UserRole)

    def getCurrentState(self, refresh=None):
        state = self.db.getCurrentState(date=self.getDateFrom(date_only=True))
        if state is not None:
            self._total = state[0]
            if not refresh:
                self._found = state[1]
            self._ready = state[2]

    """  Page  """

    def removeDBTable(self):
        self.tableResults.clear()

        for row in reversed(range(self.tableResults.rowCount())):
            self.tableResults.removeRow(row)

        self.tableResults.setRowCount(0)
        self.tableResults.setColumnCount(0)

    def setupDBWidgets(self):
        self.db.refresh_session()

        self.disconnectTableEvents()

        self.setupDBPageSize()
        self.setupDBFilter()
        self.setupDBStatus()
        self.setupDBTable()

        self.connectTableEvents()

        self.showCounts()

    def setupDBPageSize(self):
        self.boxPageSize.clear()

        values = getDBPageSize()

        for id, size in values:
            self.boxPageSize.addItem(size, id)

        n = _default_page_size
        self._page_size = values[n][0]

        self.boxPageSize.setCurrentIndex(n)
        
    def setupDBFilter(self):
        self.boxFilterColumn.clear()

        values = getDBFilterColumn()

        for id, column in values:
            self.boxFilterColumn.addItem(column, id)

        n = _default_filter_column
        self._filter_column = values[n][0]

        self.boxFilterColumn.setCurrentIndex(n)

    def setupDBStatus(self):
        self.boxStatus.clear()

        for id, status in getDBStatus():
            self.boxStatus.addItem(self.style().standardIcon(_default_status_icons[id]), status, id)

        #self.boxStatus.setMaxCount(100)
        #for id in range(69):
        #    status = 'Статус: %s' % id
        #    self.boxStatus.addItem(self.style().standardIcon(id), status, id)

        self.boxStatus.setCurrentIndex(0)

    def setupDBTable(self):
        if self.db is None:
            return

        self.tableResults.hide()
        self.tableResults.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.tableResults.setSortingEnabled(True)

        if self.tableResults.rowCount():
            self.removeDBTable()

        self.init_form(no_query=True)

        if not self._page:
            self._page = 1

        out, headers, res, query, pages = self.db.getCasesPage(page=self._page, size=self._page_size, 
            filter=(self._filter_column, self._filter_text), date=self.getDateFrom(date_only=True))

        columns = [''] + [x['title'] for x in headers if x['visible']]

        self.tableResults.setColumnCount(len(columns))
        self.tableResults.setHorizontalHeaderLabels(columns)

        self.showDBPage(out, headers)

        self.tableResults.show()

        self._page_count = pages

        self.showPageNumber()
        self.showSelectedMessage()

        if not out:
            reply = QtGui.QMessageBox.critical(self, 'Информация Базы Данных', 
                'По данному запросу данные отсутствуют.')

        if IsDebug:
            self.logger.out('show')

    def showDBPage(self, data, headers):
        self.tableResults.setRowCount(len(data))

        for row, items in enumerate(data):
            self.showRowItems(row, items, headers)

        self.tableResults.resizeColumnsToContents()

        col = 1
        for n, header in enumerate(headers):
            if header.get('visible'):
                if 'size' in header:
                    self.tableResults.setColumnWidth(col, header.get('size'))
                col += 1

        self.tableResults.setColumnWidth(0, 30)

    """  Data Items  """

    def removeDBRow(self, row):
        for col in reversed(range(self.tableResults.columnCount())):
            #item = self.tableResults.item(row, col)
            self.tableResults.removeCellWidget(row, col)
            #del item
            #item = None

    def showDataItems(self):
        ids = self.get_ids(self._selected_id)

        self._show = True

        out = self.db.getCaseItems(self._selected_id)

        self.textFromName.setText(_get_items(out['FromName']))
        self.textToName.setText(_get_items(out['ToName']))
        self.textToAddress.setText(_get_items(out['ToAddress']))
        self.textManager.setText(_get_items(out['Managers']))

        self.showEmails(ids['pid'])
        self.showPhones(ids['pid'])

        self.setFormState()

        self._show = False

    def showRowItems(self, row, items, headers, refresh=False):
        self._show = True

        if not refresh:
            self.removeDBRow(row)

        id, values = items
        ids = self.get_ids(id)

        background = QtGui.QBrush(QtGui.QColor(_default_status_backgrounds[ids['status']]))
        background.setStyle(QtCore.Qt.SolidPattern)

        if not refresh:
            item0 = QtGui.QTableWidgetItem()
            flags = item0.flags()
            flags = flags & ~QtCore.Qt.ItemIsEditable
            flags = flags | QtCore.Qt.ItemIsUserCheckable
            item0.setFlags(flags)
        else:
            item0 = self.tableResults.item(row, 0)

        item0.setData(QtCore.Qt.UserRole, id)
        item0.setBackground(background)

        checked = False
        col = 1

        for n, header in enumerate(headers):
            if header.get('visible'):
                v = values[n]
                if 'value' in header:
                    v = header.get('value')(v)
                if 'checked' in header:
                    checked = header.get('checked')(v, ids['status'])
                if 'format' in header and v:
                    f = header.get('format')
                    v = f.format(v).replace(',', ' ') + ' '
                elif 'bool' in header:
                    v = header.get('bool').split(':')[v and 1 or 0]
                else:
                    v = str(v)

                if not refresh:
                    item = QtGui.QTableWidgetItem()
                    flags = item.flags()
                    flags = flags & ~QtCore.Qt.ItemIsEditable
                    flags = flags & ~QtCore.Qt.ItemIsUserCheckable
                    item.setFlags(flags)
                else:
                    item = self.tableResults.item(row, col)

                item.setText(v)
                item.setBackground(background)

                if not refresh:
                    if 'align' in header and v:
                        if header.get('align') == 'right':
                            item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                        if header.get('align') == 'center':
                            item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)
                
                    self.tableResults.setItem(row, col, item)

                col += 1

        if not refresh:
            item0.setCheckState(checked and QtCore.Qt.Checked or QtCore.Qt.Unchecked)
            self.tableResults.setItem(row, 0, QtGui.QTableWidgetItem(item0))

            if checked:
                self._selected_items += 1

        self._show = False

    def refreshRowItems(self):
        current_row = self.tableResults.currentRow()

        out, headers, res, query, pages = self.db.getCasesPageItem(self._selected_id)

        if len(out) != 1:
            return

        self.showRowItems(current_row, out[0], headers, refresh=True)

    """  Emails  """

    def showEmails(self, pid):
        out, res = self.db.getEmails(pid=pid)

        self.viewEmails.clear()

        for id, value, selected, uri in out:
            item = QtGui.QListWidgetItem(value)
            item.setData(QtCore.Qt.UserRole, id)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
            item.setCheckState(selected and QtCore.Qt.Checked or QtCore.Qt.Unchecked)
            self.setListItemDecoration(item)

            self.viewEmails.addItem(item)

    def emailClicked(self, item):
        #reply = QtGui.QMessageBox.information(self, "Email clicked", '%s %s' % (item.data(QtCore.Qt.UserRole), item.checkState()))
        self.buttonEditEmail.setDisabled(False)
        self.buttonRemoveEmail.setDisabled(False)
        self._selected_email = item

    def emailChanged(self, item):
        self.db.setItemSelected('email', item.data(QtCore.Qt.UserRole), item.checkState())

    def newEmail(self):
        if self._selected_id is None:
            return

        ids = self.get_ids(self._selected_id)
        value, ok = QtGui.QInputDialog.getText(self, "Добавить Email", "Email:", QtGui.QLineEdit.Normal, "")

        if ok and value:
            if self.db.addDataItem('email', value, id=self._selected_id):
                self.showEmails(ids.get('pid'))
                self.showMessage("Информация в БД", 'Email. Изменения сохранены.', 
                    detailed_text='%s' % value)

    def editEmail(self):
        if self._selected_email is None:
            return

        item = self._selected_email
        value, ok = QtGui.QInputDialog.getText(self, "Изменить Email", "Email:", QtGui.QLineEdit.Normal, item.text())

        if ok and value:
            if self.db.changeDataItem('email', item.data(QtCore.Qt.UserRole), value):
                item.setText(value)

    def removeEmail(self, item=None):
        if self._selected_id is None or self._selected_email is None:
            return

        ids = self.get_ids(self._selected_id)
        item = self._selected_email

        row = self.viewEmails.currentRow()
        #n = self.viewEmails.indexFromItem(item)
        if row == self.viewEmails.count()-1:
            row -= 1

        if self.db.removeDataItem('email', item.data(QtCore.Qt.UserRole)):
            self.showEmails(ids.get('pid'))

        self.viewEmails.setCurrentRow(row)
        self._selected_email = self.viewEmails.currentItem()

        #self._selected_email = self.viewEmails.item(n)
        self.viewEmails.setItemSelected(self._selected_email, True)
        self.viewEmails.setFocus()

    """  Phones  """

    def showPhones(self, pid):
        out, res = self.db.getPhones(pid=pid)

        self.viewPhones.clear()

        for id, value, selected, uri in out:
            item = QtGui.QListWidgetItem(value)
            item.setData(QtCore.Qt.UserRole, id)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
            item.setCheckState(selected and QtCore.Qt.Checked or QtCore.Qt.Unchecked)
            self.setListItemDecoration(item)

            self.viewPhones.addItem(item)

    def phoneClicked(self, item):
        #reply = QtGui.QMessageBox.information(self, "Phone clicked", '%s %s' % (item.data(QtCore.Qt.UserRole), item.checkState()))
        self.buttonEditPhone.setDisabled(False)
        self.buttonRemovePhone.setDisabled(False)
        self._selected_phone = item

    def phoneChanged(self, item):
        self.db.setItemSelected('phone', item.data(QtCore.Qt.UserRole), item.checkState())

    def newPhone(self):
        if self._selected_id is None:
            return

        ids = self.get_ids(self._selected_id)
        value, ok = QtGui.QInputDialog.getText(self, "Добавить Phone", "Phone:", QtGui.QLineEdit.Normal, "")

        if ok and value != '':
            if self.db.addDataItem('phone', value, id=self._selected_id):
                self.showPhones(ids.get('pid'))
                self.showMessage("Информация в БД", 'Phone. Изменения сохранены.', 
                    detailed_text='%s' % value)

    def editPhone(self):
        if self._selected_phone is None:
            return

        item = self._selected_phone
        value, ok = QtGui.QInputDialog.getText(self, "Изменить Phone", "Phone:", QtGui.QLineEdit.Normal, item.text())

        if ok and value:
            if self.db.changeDataItem('phone', item.data(QtCore.Qt.UserRole), value):
                item.setText(value)

    def removePhone(self, item=None):
        if self._selected_id is None or self._selected_phone is None:
            return

        ids = self.get_ids(self._selected_id)
        item = self._selected_phone

        row = self.viewPhones.currentRow()
        if row == self.viewPhones.count()-1:
            row -= 1

        if self.db.removeDataItem('phone', item.data(QtCore.Qt.UserRole)):
            self.showPhones(ids.get('pid'))

        self.viewPhones.setCurrentRow(row)
        self._selected_phone = self.viewPhones.currentItem()
        self.viewPhones.setItemSelected(self._selected_phone, True)
        self.viewPhones.setFocus()

    # ------------------------------
    #   Service Thread Connections
    # ------------------------------

    def modX_init(self, progress):
        if not progress:
            return

        if 'top' in progress:
            self.modX_top_count = progress['top'][0]
            self.progressBarTop.setMaximum(progress['top'][1])
            self.progressBarTop.setValue(self.modX_top_count)

            if progress['top'][2]:
                self.setTextValue(self.labelTopProgress, progress['top'][2])
                self.show_form('top')

        if 'bottom' in progress:
            self.modX_bottom_count = progress['bottom'][0]
            self.progressBarBottom.setMaximum(progress['bottom'][1])
            self.progressBarBottom.setValue(self.modX_bottom_count)

            if progress['bottom'][2]:
                self.setTextValue(self.labelBottomProgress, progress['bottom'][2])
                self.show_form('bottom')

        self.modX_ready = True

    def modX_error(self, code, msg=None):
        self.modX_stop()

        reply = QtGui.QMessageBox.question(self, _service_messages['error'], 
            '%s%s\n%s?' % (code, msg and '\n'+msg or '', _service_messages['continue']),
            QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel)

        self.hide_form()
        self.refresh()

        if reply == QtGui.QMessageBox.Yes:
            self.modXThread.start()
        else:
            self.modX_finish()

    def modX_start(self):
        if self.modXThread is None or not self.modX_ready:
            self._init_service()

            self._found = 0
            self.countFound.setText(str(self._found))

        self.startClock()

        self._started = True
        self.modXThread.start()

    def modX_stop(self):
        if self.modXThread is None or not self.modX_ready:
            return

        self._started = False
        self.modXThread.stop()

        self.stopClock()

    def modX_progress(self, progress):
        if not progress:
            return

        if 'top' in progress:
            self.modX_top_count = progress['top'][0]
            self.progressBarTop.setValue(self.modX_top_count)
            self.setTextValue(self.labelTopProgress, progress['top'][2])

        if 'bottom' in progress:
            self.modX_bottom_count = progress['bottom'][0]
            self.progressBarBottom.setValue(self.modX_bottom_count)
            #if progress['top'][1] > self.progressBarTop.maximum():
            #    self.progressBarTop.setMaximum(progress['top'][1])
            self.setTextValue(self.labelBottomProgress, progress['bottom'][2])

        self.show_form('top:bottom')

        if 'found' in progress:
            self._found = progress['found']

        if 'ready' in progress:
            self._ready = progress['ready']

        if not IsSelfTest:
            self.showCounts(refresh=True)

    def modX_finish(self):
        self.modX_ready = False
        self._started = False

        if IsDebug:
            self.logger.out('finish')

        self.stopClock()

    def modX_finished(self):
        if not (self._started or self.modX_ready):
            del self.modXThread
            self.modXThread = None

            #self._init_service()

        if IsDebug:
            self.logger.out('finished')

        self.hide_form()
        self.refresh()

 
class AppDialogSettings(QtGui.QDialog, Ui_DialogSettings):

    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.setupUi(self)

    def _init_state(self, options):
        for settings in options:
            for key in options.get(settings):
                ob = getattr(self, 'checkBox%s' % key.capitalize())
                if ob is not None and options[settings][key]:
                    ob.setChecked(True)

        self.dialSearchLevel.setProperty("value", _default_count)
        #self.lcdNumberSearchLevel.setValue(_default_count)
        self.spinBoxThreshold.setValue(_default_threshold)
        self.checkBoxLoadingDisable.setChecked(True)

    def isLoadingDisabled(self):
        return self.checkBoxLoadingDisable.isChecked()

    def getState(self):
        options = {}
        for settings in _default_options:
            options[settings] = {}
            for key in _default_options[settings]:
                ob = getattr(self, 'checkBox%s' % key.capitalize())
                value = ob is not None and ob.isChecked() or False
                options[settings][key] = value
        options['count'] = self.lcdNumberSearchLevel.intValue()
        options['threshold'] = self.spinBoxThreshold.value()
        return options

    def accept(self):
        self.emit(QtCore.SIGNAL('settings'))
        self.close()


if __name__ == "__main__":
    logger = Logger(False)

    app = QtGui.QApplication(sys.argv)

    myapp = AppMainWindow()
    myapp._init_state('Plastique', logger=logger)
    myapp.show()
    sys.exit(app.exec_())

    logger.close()