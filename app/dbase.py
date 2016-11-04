#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import re
from operator import itemgetter

from sqlalchemy import create_engine, func, asc, desc, and_, or_, text as stext
from sqlalchemy.orm import sessionmaker

from config import (
     Config, ERRORLOG as errorlog, SQLALCHEMY_DATABASE_URI, IsDebug, IsDeepDebug)

from .logger import print_to, print_exception, log, EOR
from .models import (
     PAGE_SIZE, FILTER_COLUMNS, STATUS, CLAIM_BASE,
     Pagination, Case, Plaintiff, Respondent, Participant, Email, Phone, Manager, WebPage, Proxy,
     create_db)
from .utils import (
     cdate, get_domain, get_formatted_email, get_formatted_phone, round_up)

_global_spended_time_limit = Config['GLOBAL'].getint('spended_time_limit')
_global_max_html_size = Config['GLOBAL'].getint('max_html_size')

_global_claim_min = 400000


def _isClaimChecked(value, status):
    return status==0 and value > _global_claim_min

def _claimValue(value):
    return value / CLAIM_BASE

def _cdate(value):
    return value.split('T')[0]


_query_views = { \
    'log' : ( \
        'cases:id', 'cases:reg_date', 'cases:CaseId', 'cases:CaseType', 
        'cases:Date', 
        'participants:id', 'participants:Name', 'cases:claim', 'participants:Address', 'cases:CaseNumber', 
        'cases:started', 'respondents:status', 
    )
}

_query_headers = { \
    'cases' : ( \
        ('id', 'reg_date', 'CaseId', 'CaseType', 'Date', 'CaseNumber', 'CourtName', 'claim', 'started', 'status', ),
        {
            'id' : {
                'visible' : 0,
            },
            'reg_date' : {
                'title'   : 'Дата регистрации',
                'visible' : 0,
            },
            'CaseId' : {
                'visible' : 0,
            },
            'CaseType' : {
                'visible' : 0,
            },
            'Date' : {
                'title'   : 'Дата иска',
                'value'   : _cdate,
                'align'   : 'center',
                'visible' : 1,
            },
            'CaseNumber' : {
                'title'   : 'Номер дела',
                'visible' : 1,
            },
            'CourtName' : {
                'title'   : 'Суд',
                'visible' : 1,
            },
            'claim' : {
                'title'   : 'Сумма иска',
                'value'   : _claimValue,
                'checked' : _isClaimChecked,
                'format'  : '{:>20,.2f}',
                'align'   : 'right',
                'visible' : 1,
            },
            'started' : {
                'title'   : '',
                'bool'    : 'N:Y',
                'align'   : 'center',
                'visible' : 1,
            },
            'status' : {
                'title'   : 'Статус',
                'align'   : 'center',
                'size'    : 44,
                'visible' : 1,
            },
        },
    ),
    'respondents' : ( \
        ('id', 'search_query', 'output', 'doc', 'status', ), 
        {
            'id' : {
                'visible' : 0,
            },
            'search_query' : {
                'title'   : 'Поисковый запрос',
                'visible' : 1,
            },
            'output' : {
                'title'   : 'Файл с результатами поиска',
                'visible' : 1,
            },
            'status' : {
                'title'   : 'Статус',
                'align'   : 'center',
                'visible' : 1,
                'size'    : 44,
            },
        },
    ),
    'participants' : ( \
        ('id', 'reg_date', 'Name', 'Address', ),
        {
            'id' : {
                'visible' : 0,
            },
            'reg_date' : {
                'visible' : 0,
            },
            'Name' : {
                'title'   : 'Ответчик',
                'visible' : 1,
                'size'    : 432,
            },
            'Address' : {
                'title'   : 'Адрес ответчика',
                'visible' : 1,
                'size'    : 300,
            },
        },
    ),
}


def getDBPageSize():
    return [x for x in PAGE_SIZE]

def getDBFilterColumn():
    return [x[1] for x in sorted(FILTER_COLUMNS.items(), key=itemgetter(1))]

def getDBStatus():
    return [x[1] for x in sorted(STATUS.items(), key=itemgetter(1))]


class DBConnector(object):
    
    def __init__(self, echo=False, **kw):
        self.engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=echo) #, convert_unicode=True
        self.session = None

        self._debug = kw.get('debug') and True or False
        self._trace = kw.get('trace') and True or False

    def create_database(self):
        try:
            create_db()
        except:
            print_exception()
            return

        if self._debug:
            print('>>> New DB has been created successfully.')

    def close(self):
        self.close_session()

    def open_session(self):
        if self.session is None:
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
        return self.session

    def close_session(self):
        if self.session is None:
            return

        self.commit(check_session=True)

        del self.session
        self.session = None

    def refresh_session(self):
        self.close_session()
        self.open_session()

    def add(self, ob):
        if self._debug:
            print('>>> Add %s' % ob)
        self.session.add(ob)

    def delete(self, ob):
        if self._debug:
            print('>>> Delete %s' % ob)
        self.session.delete(ob)

    def commit(self, check_session=True, is_error=False):
        if is_error:
            if self._debug:
                print('>>> Error')
            return
        if check_session:
            if not (self.session.new or self.session.dirty or self.session.deleted):
                if self._debug:
                    print('>>> No data to commit: new[%s], dirty[%s], deleted[%s]' % ( \
                        len(self.session.new), len(self.session.dirty), len(self.session.deleted)))
                return
        try:
            self.session.commit()
        except Exception as err:
            self.session.rollback()
            if self._debug:
                print('>>> Commit Error: %s' % err)
            print_to(errorlog, str(err))
        if self._debug:
            print('>>> OK')

    def getCurrentState(self, **kw):
        if not self.session:
            self.open_session()

        query = self.session.query(Case, Respondent) \
                .filter(Respondent.case_id==Case.id)

        if 'date' in kw:
            date = kw.get('date')
            query = query \
                .filter(Case.Date>=date)

        try:
            return ( \
                query.count(), 
                query.filter(Respondent.status==1).count(), 
                query.filter(Respondent.status==2).count(), 
                0,
            )
        except:
            print_exception()
            self.refresh_session()
            return None

    def get_ids(self, id):
        x = id.split(':')
        return {'cid':x[0], 'rid':x[1], 'pid':x[2], 'status':int(x[3])}

    def set_ids(self, cid, rid, pid, status):
        return '%s:%s:%s:%s' % (cid, rid, pid, status)

    def _checkIsCaseExist(self, case, **kw):

        query = self.session.query(Case) \
                .filter(and_(Case.CaseId==case.CaseId, Case.CaseNumber==case.CaseNumber))

        res = query.all()

        exists = len(res) and True or False
        updated = False

        if kw and exists:
            for ob in res:
                if 'started' in kw and kw['started'] != ob.started:
                    ob.started = kw['started']
                    updated = True
                if 'claim' in kw:
                    claim = Case.get_claim(kw['claim'])
                    if claim != ob.claim:
                        ob.claim = claim
                        updated = True

        if IsDebug:
            print('--> %s %s' % (case.CaseNumber, exists and 'exists' or 'updated' and updated or 'new'))

        return updated and 1 or exists and 2 or 0

    def _checkExistedParticipant(self, participant, **kw):

        query = self.session.query(Participant) \
                .filter(and_(Participant.Name==participant.Name, Participant.OrganizationForm==participant.OrganizationForm))

        ob = query.first()

        if ob is None:
            return 0, participant
        else:
            return 1, ob

    def shouldItemBeSelected(self, id, check_status=None):
        ids = self.get_ids(id)

        case = self.getCaseById(id=ids['cid'])
        if case is None:
            return False

        if check_status:
            respondent = self.getRespondentById(id=ids['rid'])
            status = respondent is not None and respondent.status or 0
        else:
            status = 0

        return _isClaimChecked(_claimValue(case.claim), status)

    def setStatus(self, id, status):
        ids = self.get_ids(id)

        respondent = self.getRespondentById(id=ids['rid'])

        if respondent is None:
            return

        print('set status:%s [%s]' % (status, id))

        respondent.status = status

        self.commit()

    def setItemSelected(self, mode, id, value):
        if mode == 'email':
            ob = self.getEmailById(id)
        elif mode == 'phone':
            ob = self.getPhoneById(id)

        if ob is None:
            return

        ob.selected = value and True or False

        self.commit()

    def unregister(self, id, mode=None):
        ids = self.get_ids(id)

        if not mode or mode == 'emails':
            out, res = self.getEmails(pid=ids['pid'])
            for email in res:
                self.delete(email)

        if not mode or mode == 'phones':
            out, res = self.getPhones(pid=ids['pid'])
            for phone in res:
                self.delete(phone)

        if not mode or mode == 'managers':
            out, res = self.getManagers(pid=ids['pid'])
            for manager in res:
                self.delete(manager)

        if not mode:
            respondent = self.getRespondentByCaseId(cid=ids['cid'], pid=ids['pid'])
        
            if respondent is not None:
                respondent.set_status('LOAD')
                respondent.set_output('')

        self.commit()

    def register(self, mode, data, **kw):
        if not self.session:
            self.open_session()

        def _get_uri(values):
            out = ''
            dns = []
            for x in values:
                d = get_domain(x)
                if d in dns:
                    continue
                dns.append(d)
                if len(out)+len(x) < 250:
                    out += '%s%s' % (out and ';' or '', x)
                else:
                    break
            out = out.strip()
            out = out.endswith(';') and out[:-1] or out
            return out

        done = 0

        if not mode or not data:
            pass

        elif mode == 'proxy':
            address, data = data

            res = self.session.query(Proxy).filter_by(address=address).all()

            if not res:
                proxy = Proxy(address, data)
                self.add(proxy)
            elif data.get('online'):
                proxy = res[0]
                if proxy.kind != 'default':
                    proxy.response = data.get('response')
                    proxy.online = True
                else:
                    proxy = None
            else:
                proxy = None

            if proxy is not None:
                self.commit()

            done = 1

        elif mode == 'output':
            #
            #   Данные поисковой системы
            #
            id = kw.get('id')
            domain, uri, output, output_path = data

            if id and output:
                emails, phones, addresses, managers = output
            else:
                return 0

            ids = self.get_ids(id)

            for v, u in emails:
                email = Email(get_formatted_email(v), uri=_get_uri(u))
                email.participant_id = ids['pid']
                self.add(email)

            for v, u in phones:
                phone = Phone(get_formatted_phone(v), uri=_get_uri(u))
                phone.participant_id = ids['pid']
                self.add(phone)

            for v, u in managers:
                manager = Manager(v, uri=_get_uri(u))
                manager.participant_id = ids['pid']
                self.add(manager)

            respondent = self.getRespondentByCaseId(cid=ids['cid'], pid=ids['pid'])
            if respondent is None:
                return

            respondent.set_status('CONTROL')
            respondent.set_output(output_path)

            self.commit()

            done = 1

        elif mode == 'case':
            #
            #   Дело
            #
            case = Case(court=kw.get('court'), code=kw.get('code'), claim=kw.get('claim'), started=kw.get('started'), 
                        columns=data)

            state = self._checkIsCaseExist(case, **kw)

            if not state:
                self.add(case)

                for x in data['Plaintiffs']:
                    participant = Participant(x)

                    exists, p = self._checkExistedParticipant(participant)

                    if not exists:
                        self.add(participant)
                    else:
                        participant = p

                    self.add(Plaintiff(case, participant))

                for x in data['Respondents']:
                    participant = Participant(x)

                    exists, p = self._checkExistedParticipant(participant)

                    if not exists:
                        self.add(participant)
                    else:
                        participant = p

                    self.add(Respondent(case, participant))

                done = 1
            else:
                case = None

            if state < 2:
                self.commit()

        elif mode == 'respondent':
            id = kw.get('id')
            name, address, manager = data

            ids = self.get_ids(id)

            participant = self.getParticipantById(id=ids['pid'])
            if participant is None:
                return

            participant.update(name=name, address=address)

            if manager:
                self.unregister(id, 'managers')
                manager = Manager(manager, uri=None)
                manager.participant_id = ids['pid']
                self.add(manager)

            self.commit()

            done = 1

        elif mode == 'manager':
            id = kw.get('id')

        elif mode == 'uri':
            uri, html_size, html_time, spended_time, rating = data

            if not uri:
                return 0

            exists = self.session.query(WebPage.id).filter_by(uri=uri).count()

            if not exists:
                max_time = max(html_time, spended_time)

                if max_time > _global_spended_time_limit or html_size > _global_max_html_size:
                    webpage = WebPage(uri, html_size, max_time)
                    self.add(webpage)

                    self.commit()

            done = 1

        return done

    def addDataItem(self, mode, data, **kw):
        done = 0
        id = kw.get('id')
        ids = self.get_ids(id)
        
        if mode and ids['pid'] and data:
            if mode == 'email':
                ob = Email(get_formatted_email(data), uri='')
            elif mode == 'phone':
                ob = Phone(get_formatted_phone(data), uri='')

            if ob is not None:
                ob.participant_id = ids['pid']
                self.add(ob)

                self.commit()
                done = 1

        return done

    def changeDataItem(self, mode, id, data):
        done = 0
        
        if mode and id and data:
            if mode == 'email':
                ob = self.getEmailById(id)
            elif mode == 'phone':
                ob = self.getPhoneById(id)

            if ob is not None:
                ob.value = data

                self.commit()
                done = 1

        return done

    def removeDataItem(self, mode, id):
        done = 0
        
        if id:
            if mode == 'email':
                ob = self.getEmailById(id)
            elif mode == 'phone':
                ob = self.getPhoneById(id)

            if ob is not None:
                self.delete(ob)

                self.commit()
                done = 1

        return done

    def removeCaseById(self, id):
        done = 0

        case = self.session.query(Case).filter(Case.id==id).one()
        
        if case is not None:
            for ob in self.session.query(Plaintiff).filter(Plaintiff.case_id==id).all():
                self.delete(ob)
            for ob in self.session.query(Respondent).filter(Respondent.case_id==id).all():
                self.delete(ob)

            self.delete(case)

            self.commit()
            done = 1

        return done

    def getStatuses(self):
        return STATUS

    def getViewHeaders(self, view):
        headers = []
        for key in _query_views[view]:
            table, field = key.split(':')
            seq, mapper = _query_headers[table]
            header = field in seq and mapper[field].copy() or {}
            header['id'] = field
            header['table'] = table
            headers.append(header)
        return headers

    def getCasesPage(self, view='log', page=1, size=50, with_log=None, show=False, **kw):
        if not self.session:
            self.open_session()

        query = self.session.query(Case, Respondent, Participant) \
                .filter(Respondent.case_id==Case.id) \
                .filter(Respondent.participant_id==Participant.id)

        if 'rid' in kw:
            query = query \
                .filter(Respondent.id==kw.get('rid'))
        else:
            if 'filter' in kw:
                column, text = kw.get('filter')
                if text:
                    if column == 0:
                        s = '%' + text + '%'
                        query = query \
                            .filter(Participant.Name.like(s))
                    elif column == 1:
                        m = re.search(r'([<>=]+?)([\d]+)', text)
                        items = m and [x for x in m.groups() if x] or []
                        if len(items) < 2:
                            items = ['=', text]
                        s = int(items[-1])*CLAIM_BASE
                        z = len(items) > 1 and ''.join(items[0:-1]) or '='
                        query = query \
                            .filter(stext("cases.claim%s%s" % (z, s)))
                    elif column == 2:
                        s = '%' + text + '%'
                        query = query \
                            .filter(Participant.Address.like(s))
                    elif column == 3:
                        s = text
                        query = query \
                            .filter(Case.CaseNumber.like(s))
                    else:
                        column = -1
                else:
                    column = -1
            else:
                column = -1
            
            if column == -1:
                query = query \
                    .filter(Case.claim >= _global_claim_min*CLAIM_BASE)

            if 'date' in kw:
                date = kw.get('date')
                query = query \
                    .filter(Case.Date >= date)

            query = query \
                .order_by(desc(Case.claim))

        if page and size:
            res = query[(page-1)*size:page*size]
            count = query.count()
            pages = round_up(count/size)
        else:
            res = query.all()
            count = len(res)
            pages = 1

        out = []

        headers = self.getViewHeaders(view)

        for c, r, p in res:
            id = self.set_ids(c.id, r.id, p.id, r.status)
            x = '--> %s %s %s [%s] = %s' % (id, p.Name, p.Address, c.CaseNumber, c.claim/CLAIM_BASE)

            item = []
            for n, key in enumerate(_query_views[view]):
                table, field = key.split(':')
                value = getattr(table == 'cases' and c or table == 'participants' and p or r, field)
                header = headers[n]
                item.append(value)

            out.append((id, tuple(item)))
            if show:
                print(x)

        if with_log:
            log(os.path.join(Config['OUTPUT'].get('log_folder'), with_log), out, mode='w', bom=True, end_of_line=EOR)

        return out, headers, res, query, pages

    def getCasesPageItem(self, id):
        ids = self.get_ids(id)
        return self.getCasesPage(page=0, rid=ids['rid'])

    def getCaseItems(self, id, show=False):
        if not self.session:
            self.open_session()

        out = {'FromName':[], 'FromAddress':[], 'ToName':[], 'ToAddress':[], 'Managers': []}

        if not id:
            return out, None

        ids = self.get_ids(id)

        query = self.session.query(Case, Plaintiff, Participant) \
                .filter(Plaintiff.case_id==Case.id) \
                .filter(Plaintiff.participant_id==Participant.id) \
                .filter(Case.id==ids['cid'])

        res = query.all()

        for c, t, p in res:
            out['FromName'].append(p.Name)
            out['FromAddress'].append(p.Address)

            if show:
                print('>>> %s = %s' % (p.Name, p.Address))

        query = self.session.query(Case, Respondent, Participant) \
                .filter(Respondent.case_id==Case.id) \
                .filter(Respondent.participant_id==Participant.id) \
                .filter(Case.id==ids['cid']) \
                .filter(Respondent.id==ids['rid'])

        res = query.all()

        for c, r, p in res:
            out['ToName'].append(p.Name)
            out['ToAddress'].append(p.Address)

            if show:
                print('--> %s = %s' % (p.Name, p.Address))

        res, managers = self.getManagers(pid=ids['pid'])
        
        for m in managers:
            out['Managers'].append(m.value)

        return out

    def getRespondentByCaseId(self, cid, pid=None, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Respondent) \
                .filter(Respondent.case_id==cid)

        if pid is not None:
            query = query \
                .filter(Respondent.participant_id==pid)

        ob = query.one()

        if ob is not None:
            if show:
                print('--> %s = %s' % (ob.case.CaseId, ob.participant.Name))

        return ob

    def getRespondentById(self, id, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Respondent) \
                .filter(Respondent.id==id)

        ob = query.one()

        if ob is not None:
            if show:
                print('--> %s = %s' % (ob.Name, ob.Address))

        return ob

    def getRespondentByCase(self, id, with_log=None, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Case, Participant) \
                .filter(Respondent.participant_id==Participant.id) \
                .filter(Case.id==Respondent.case_id) \
                .filter(Case.id==id)

        res = query.all()
        out = []

        for c, p in res:
            x = '--> %s %s [%s] = %s' % (p.Name, p.Address, c.CaseNumber, c.claim/CLAIM_BASE)
            out.append(x)
            if show:
                print(x)

        if with_log:
            log(os.path.join(Config['OUTPUT'].get('log_folder'), with_log), out, mode='w', bom=True, end_of_line=EOR)

        return out, res, query

    def getSortedRespondent(self, with_log=None):
        if not self.session:
            self.open_session()

        query = self.session.query(Case, Participant) \
                .filter(Respondent.participant_id==Participant.id) \
                .filter(Case.id==Respondent.case_id) \
                .group_by(Participant.id) \
                .order_by(desc(Case.claim))

        res = query.all()
        out = []

        for c, p in res:
            x = '--> %s %s [%s] = %s' % (p.Name, p.Address, c.CaseNumber, c.claim/CLAIM_BASE)
            out.append(x)
            print(x)

        if with_log:
            log(os.path.join(Config['OUTPUT'].get('log_folder'), with_log), out, mode='w', bom=True, end_of_line=EOR)

        return out, res, query

    def getCaseById(self, id, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Case) \
                .filter(Case.id==id)

        ob = query.one()

        if ob is not None:
            if show:
                print('--> %s = %s' % (ob.CaseId, ob.CaseNumber))

        return ob

    def getParticipantById(self, id, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Participant) \
                .filter(Participant.id==id)

        ob = query.one()

        if ob is not None:
            if show:
                print('--> %s = %s' % (ob.Name, ob.Address))

        return ob

    def getEmailById(self, id, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Email) \
                .filter(Email.id==id)

        ob = query.one()

        if ob is not None:
            if show:
                print('--> %s: [%s] %s' % (ob.id, ob.selected and '1' or '0', ob.value))

        return ob

    def getPhoneById(self, id, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Phone) \
                .filter(Phone.id==id)

        ob = query.one()

        if ob is not None:
            if show:
                print('--> %s: [%s] %s' % (ob.id, ob.selected and '1' or '0', ob.value))

        return ob

    def getManagerById(self, id, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Manager) \
                .filter(Manager.id==id)

        ob = query.one()

        if ob is not None:
            if show:
                print('--> %s: [%s] %s' % (ob.id, ob.selected and '1' or '0', ob.value))

        return ob

    def getEmails(self, id=None, pid=None, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Email) \
            .filter(and_(Email.value != None, Email.value != ''))

        if id is not None:
            query = query \
                .filter(Email.id==id)
        if pid is not None:
            query = query \
                .filter(Email.participant_id==pid)

        def _get_email_key(ob):
            v = ob.value.split('@')
            return len(v) == 2 and ('%s:%s' % (v[1], v[0])) or v

        res = query.all()
        res = dict([(ob, _get_email_key(ob)) for ob in res])
        res = [ob for ob, key in sorted(res.items(), key=itemgetter(1))]

        out = []

        for e in res:
            x = (e.id, e.value, e.selected, e.uri)
            out.append(x)
            if show:
                print('--> %s: [%s] %s' % (e.id, e.selected and '1' or '0', e.value))

        return out, res

    def getPhones(self, id=None, pid=None, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Phone)

        if id is not None:
            query = query \
                .filter(Phone.id==id)
        if pid is not None:
            query = query \
                .filter(Phone.participant_id==pid)

        query = query \
            .order_by(Phone.id)

        res = query.all()
        out = []

        for p in res:
            x = (p.id, p.value, p.selected, p.uri)
            out.append(x)
            if show:
                print('--> %s: [%s] %s' % (p.id, p.selected and '1' or '0', p.value))

        return out, res

    def getManagers(self, id=None, pid=None, show=False):
        if not self.session:
            self.open_session()

        query = self.session.query(Manager)

        if id is not None:
            query = query \
                .filter(Manager.id==id)
        if pid is not None:
            query = query \
                .filter(Manager.participant_id==pid)

        query = query \
            .order_by(Manager.id)

        res = query.all()
        out = []

        for m in res:
            x = (m.id, m.value, m.selected, m.uri)
            out.append(x)
            if show:
                print('--> %s: [%s] %s' % (m.id, m.selected and '1' or '0', m.value))

        return out, res

    def isOutputEnabled(self, mode, id=None, cid=None, pid=None, show=False):
        if not self.session:
            self.open_session()

        enabled = False

        query = self.session.query(Respondent)

        if id is not None:
            query = query \
                .filter(Respondent.id==id)
        else:
            if cid is not None:
                query = query \
                    .filter(Respondent.case_id==cid)
            if pid is not None:
                query = query \
                    .filter(Respondent.participant_id==pid)
            if not (cid and pid):
                query = query \
                    .order_by(desc(Respondent.id))

        res = query.all()

        ob = len(res) == 1 and res[0] or None

        if ob is not None:
            if mode == 'output':
                value = ob.output
            else:
                value = ob.doc
            enabled = value and True or False
            if show:
                print('--> %s [%s] = %s' % (ob.id, enabled and '1' or '0', value))

        return enabled

    def isUriEnabled(self, uri, level=None):
        #
        # Check exists URI of given level domain
        #
        if not self.session:
            self.open_session()

        enabled = False

        exists = self.session.query(WebPage.id).filter_by(uri=uri).count()

        if not exists and level is not None:
            domain = get_domain(uri, level)
            
            res = self.session.query(WebPage.id).filter(WebPage.uri.like('%'+domain+'%')).all()

            if len(res):
                exists = True

        enabled = not exists and True or False
        
        return enabled

    def getOutput(self, mode, id, show=False):
        if not self.session:
            self.open_session()

        output = ''

        query = self.session.query(Respondent) \
                .filter(Respondent.id==id)

        ob = query.one()

        if ob is not None:
            if mode == 'output':
                value = ob.output
            else:
                value = ob.doc
            enabled = value and True or False
            if show:
                print('--> %s [%s] = %s' % (ob.id, enabled and '1' or '0', value))

            output = value

        return output

    def getValidProxy(self, current_proxy=None):
        #
        # Get next valid proxy
        #
        if not self.session:
            self.open_session()

        if current_proxy == -1:
            return None

        #if current_proxy is not None and current_proxy.type != 'default':
        #    current_proxy.online = False
        #    self.commit()

        query = self.session.query(Proxy) \
            .filter(Proxy.online==True).filter(Proxy.response < 10.0) \
            .order_by(Proxy.response)

        res = query.all()

        ob = None
        is_break = False
        for n in range(len(res)):
            if current_proxy is None or is_break:
                ob = res[n]
                break
            else:
                if res[n].address == current_proxy.address:
                    is_break = True

        return ob

    def updateProxy(self, id, response, online):
        pass
