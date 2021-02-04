from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import pytz

engine = create_engine('sqlite:///homething.db')
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    device = Column(String, index=True)
    datetime = Column(DateTime)
    event = Column(String)
    uptime = Column(Integer)


class MemoryLog(Base):
    __tablename__ = "memorylogs"
    id = Column(Integer, primary_key=True)
    device = Column(String, index=True)
    datetime = Column(DateTime, index=True)
    free = Column(Integer)
    min_free = Column(Integer)


Base.metadata.create_all(engine)


def add_memory_log(device, free, min_free):
    now = datetime.datetime.now(pytz.utc)
    log = MemoryLog(datetime=now, device=device, free=free, min_free=min_free)
    session = Session()
    try:
        session.add(log)
        session.commit()
    except:
        session.rollback()
        raise


def get_memory_logs(device, from_time, to_time):
    return Session().query(MemoryLog).filter(MemoryLog.device == device, MemoryLog.datetime >= from_time,
                                             MemoryLog.datetime <= to_time).order_by(MemoryLog.datetime.asc())


def add_event(device, event, uptime):
    timestamp = datetime.datetime.now(pytz.utc)
    log = Event(datetime=timestamp, device=device, event=event, uptime=uptime)
    session = Session()
    try:
        session.add(log)
        session.commit()
    except:
        session.rollback()
        raise


def get_events_query(device):
    return Session().query().select_from(Event).filter_by(device=device)

