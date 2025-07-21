from . import BasePlugin
from .records import RecordPlugin

class BS240:
    header = BS240HeaderRecord()

class BS240HeaderRecord(RecordPlugin):
    
    def __init__(self, record_type='H', wrapper=HeaderWrapper):
        super(self, BS240HeaderRecord).__init__(record_type, wrapper)
        
