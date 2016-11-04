# -*- coding: utf-8 -*-

#import os
#import sys
#import re
from datetime import datetime

#basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
#sys.path.append(basedir)

from sqlalchemy import Column, BigInteger, Integer, String, Unicode, Boolean, DateTime, Float, ForeignKey
from sqlalchemy import create_engine

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import mapper, relationship, backref

from config import (
     Config, ERRORLOG as errorlog, SQLALCHEMY_DATABASE_URI, PAGE_SIZE, FILTER_COLUMNS, STATUS,
     KAD_CASE_KEYS, KAD_PARTICIPANT_KEYS)

from .utils import out, cid, cdate, clean

Base = declarative_base()

CLAIM_BASE = 100

##  ------------
##  Help Classes
##  ------------

class Pagination(object):
    #
    # Simple Pagination
    #
    def __init__(self, page, per_page, total, value, sql):
        self.page = page
        self.per_page = per_page
        self.total = total
        self.value = value
        self.sql = sql

    @property
    def query(self):
        return self.sql

    @property
    def items(self):
        return self.value

    @property
    def current_page(self):
        return self.page

    @property
    def pages(self):
        return int(ceil(self.total / float(self.per_page)))

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    def get_page_params(self):
        return (self.current_page, self.pages, self.per_page, self.has_prev, self.has_next, self.total,)

    def iter_pages(self, left_edge=1, left_current=0, right_current=3, right_edge=1):
        last = 0
        out = []
        for num in xrange(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    out.append(None)
                out.append(num)
                last = num
        return out

##  ==========================
##  Objects Class Construction
##  ==========================

class ExtClassMethods(object):
    """
        Abstract class methods
    """
    @classmethod
    def all(cls):
        return cls.query.all()

    @classmethod
    def get_by_id(cls, id):
        return cls.query.filter_by(id=id).first()

    @classmethod
    def print_all(cls):
        for x in cls.all():
            print(x)

    def set_status(self, name):
        self.status = STATUS[name][0]

    def set_output(self, value):
        self.output = value and value[:250] or ''

    def set_doc(self, value):
        self.doc = value and value[:250] or ''

    def set_query(self, value):
        self.search_query = value and value[:250] or ''


class Case(Base, ExtClassMethods):
    #
    #    Дело
    #
    __tablename__ = 'cases'

    id = Column(Integer, primary_key=True)
    reg_date = Column(DateTime, nullable=False, default=datetime.now(), index=True)

    Judge = Column(Unicode(120), nullable=False)
    CaseId = Column(Unicode(36), nullable=False, index=True)
    CaseType = Column(Unicode(1), default='G')
    CaseNumber = Column(Unicode(16), index=True)
    Date = Column(String(19), index=True)
    CourtName = Column(Unicode(60))
    IsSimpleJustice = Column(Boolean, default=False)

    status = Column(Integer, nullable=False, default=0, index=True)

    court = Column(String(3), nullable=False, index=True)
    code = Column(String(1), nullable=False, index=True)
    claim = Column(BigInteger, nullable=False, default=0)
    started = Column(Boolean, default=False)

    #plaintiffs = relationship("Plaintiff", order_by="Plaintiff.id", backref="case")
    #respondents = relationship("Respondent", order_by="Respondent.id", backref="case")

    def __init__(self, court, code, claim=0, started=False, columns=None):
        self.reg_date = datetime.utcnow()
        self.court = court
        self.code = code
        self.claim = int(claim*CLAIM_BASE)
        self.started = started
        self.set_attrs(columns)

    def __repr__(self):
        return "<Case(id='%s', number='%s', date='%s')>" % (self.CaseId, self.CaseNumber, self.Date)

    def set_attrs(self, columns=None):
        changed = False
        if columns:
            for key in KAD_CASE_KEYS:
                value = columns.get(key)
                if key == 'IsSimpleJustice':
                    value = value and True or False
                elif key == 'claim':
                    value = self.get_claim(value)
                else:
                    value = clean(value)
                setattr(self, key, value)
                changed = True
        if changed:
            self.reg_date = datetime.utcnow()

    @staticmethod
    def get_claim(value):
        return int(float(value)*100)


class Plaintiff(Base, ExtClassMethods):
    #
    #   Истец
    #
    __tablename__ = 'plaintiffs'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id'))
    participant_id = Column(Integer, ForeignKey('participants.id'))

    case = relationship('Case', backref=backref('plaintiffs', order_by=id))
    participant = relationship('Participant', backref=backref('plaintiffs'), uselist=False)

    def __init__(self, case, participant):
        self.case = case
        self.participant = participant


class Respondent(Base, ExtClassMethods):
    #
    #    Ответчик
    #
    __tablename__ = 'respondents'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id'))
    participant_id = Column(Integer, ForeignKey('participants.id'))

    case = relationship('Case', backref=backref('respondents', order_by=id))
    participant = relationship('Participant', backref=backref('respondents'), uselist=False)

    status = Column(Integer, nullable=False, default=0, index=True)

    search_query = Column(Unicode(250))
    output = Column(Unicode(250))
    doc = Column(Unicode(250))

    def __init__(self, case, participant):
        self.case = case
        self.participant = participant


class Participant(Base, ExtClassMethods):
    #
    #    Атрибуты участника дела (истца, ответчика)
    #
    __tablename__ = 'participants'

    id = Column(Integer, primary_key=True)
    reg_date = Column(DateTime, index=True)

    Name = Column(Unicode(250), nullable=False, index=True)
    Address = Column(Unicode(500))
    Inn = Column(Unicode(10))
    OrganizationForm = Column(Unicode(36))

    emails = relationship('Email', backref=backref('participant'), cascade="all, delete-orphan")
    phones = relationship('Phone', backref=backref('participant'), cascade="all, delete-orphan")
    managers = relationship('Manager', backref=backref('participant'), cascade="all, delete-orphan")

    def __init__(self, columns=None):
        self.reg_date = datetime.utcnow()
        self.set_attrs(columns)

    def __repr__(self):
        return "<Participant(name='%s')>" % (self.Name)

    def set_attrs(self, columns=None):
        changed = False
        if columns:
            for key in KAD_PARTICIPANT_KEYS:
                value = clean(columns.get(key))
                if key == 'Inn':
                    value = len(value) < 11 and value or ''
                setattr(self, key, value)
                changed = True
        if changed:
            self.reg_date = datetime.utcnow()

    def update(self, **kw):
        if 'name' in kw:
            self.Name = clean(kw.get('name'))
        if 'address' in kw:
            self.Address = clean(kw.get('address'))


class Email(Base, ExtClassMethods):
    #
    #    Почтовые адреса
    #
    __tablename__ = 'emails'

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey('participants.id'))
    reg_date = Column(DateTime, index=True)

    value = Column(String(60), nullable=False, index=True)

    selected = Column(Boolean, default=False)
    uri = Column(Unicode(250))

    def __init__(self, value, uri=None):
        self.reg_date = datetime.utcnow()
        self.value = value
        self.uri = uri

    def __repr__(self):
        return '<Email %s:%s %s [%s]>' % (cid(self), self.value, self.participant.Name, self.selected and 'Yes' or 'No')


class Phone(Base, ExtClassMethods):
    #
    #    Телефоны
    #
    __tablename__ = 'phones'

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey('participants.id'))
    reg_date = Column(DateTime, index=True)

    value = Column(String(20), nullable=False, index=True)

    selected = Column(Boolean, default=False)
    uri = Column(Unicode(250))

    def __init__(self, value, uri=None):
        self.reg_date = datetime.utcnow()
        self.value = value
        self.uri = uri

    def __repr__(self):
        return '<Phone %s:%s %s [%s]>' % (cid(self), self.value, self.participant.Name, self.selected and 'Yes' or 'No')


class Manager(Base, ExtClassMethods):
    #
    #    Менеджеры (ФИО, должность, контакты)
    #
    __tablename__ = 'managers'

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey('participants.id'))
    phone_id = Column(Integer, ForeignKey('phones.id'))
    email_id = Column(Integer, ForeignKey('emails.id'))
    reg_date = Column(DateTime, index=True)

    value = Column(Unicode(250), nullable=False, index=True)

    first_name = Column(Unicode(40))         # имя, отчество
    second_name = Column(Unicode(40))        # фамилия
    post = Column(Unicode(80))               # должность

    selected = Column(Boolean, default=False)
    uri = Column(Unicode(250))

    def __init__(self, value, uri=None):
        self.reg_date = datetime.utcnow()
        self.value = value
        self.uri = uri

    def __repr__(self):
        return '<Manager %s:%s %s [%s]>' % (cid(self), self.value, self.participant.Name, self.selected and 'Yes' or 'No')


class WebPage(Base):
    #
    #    WEB-страницы
    #
    __tablename__ = 'webpages'

    id = Column(Integer, primary_key=True)
    reg_date = Column(DateTime, nullable=False, default=datetime.now(), index=True)

    uri = Column(Unicode(250), index=True)

    size = Column(Integer, nullable=False, default=0)
    time = Column(Integer, nullable=False, default=0)

    def __init__(self, uri, size, time):
        self.reg_date = datetime.utcnow()
        self.uri = uri
        self.size = size
        self.time = time

    def __repr__(self):
        return "<WebPage(id='%s' [%s], size='%s', time='%s')>" % (cid(self), self.uri, self.size, self.time)


class Proxy(Base):
    #
    #    Proxy
    #
    __tablename__ = 'proxies'

    id = Column(Integer, primary_key=True)
    reg_date = Column(DateTime, nullable=False, default=datetime.now(), index=True)

    address = Column(String(25), index=True)

    kind = Column(Unicode(50))
    land = Column(Unicode(50))
    response = Column(Float, default=0, index=True)
    online = Column(Boolean, default=False)

    def __init__(self, address, data):
        self.reg_date = datetime.utcnow()
        self.address = address
        self.kind = data.get('kind')
        self.land = ('%s' % (data.get('land') or '')).strip()
        self.response = data.get('response')
        self.online = data.get('online')

    def __repr__(self):
        return "<Proxy(id='%s' [%s], response='%s', online='%s')>" % (cid(self), self.address, str(self.response), self.online and 'Yes' or 'No')


def create_db():
    engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)
    Base.metadata.create_all(engine)


if __name__ == '__main__':
    create_db()
