import logging
from logging import handlers
import linecache
import sys,time,os

def getdir():
    curpath = os.path.dirname(os.path.realpath(__file__))
    return curpath

def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    sErr = 'Error IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj)
    return sErr

class Logger(object):
    level_relations = {
        'debug':logging.DEBUG,
        'info':logging.INFO,
        'warning':logging.WARNING,
        'error':logging.ERROR,
        'crit':logging.CRITICAL
    }#日志级别关系映射
    def __init__(self,filename,level='info',when='d',backCount=3,fmt='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s'):
        self.logger = logging.getLogger(filename)
        format_str = logging.Formatter(fmt)#设置日志格式
        self.logger.setLevel(self.level_relations.get(level))#设置日志级别
        sh = logging.StreamHandler()#往屏幕上输出
        sh.setFormatter(format_str) #设置屏幕上显示的格式
        th = handlers.TimedRotatingFileHandler(filename=filename,when=when,backupCount=backCount,encoding='utf-8')#往文件里写入#指定间隔时间自动生成文件的处理器
        #实例化TimedRotatingFileHandler
        #interval是时间间隔，backupCount是备份文件的个数，如果超过这个个数，就会自动删除，when是间隔的时间单位，单位有以下几种：
        # S 秒
        # M 分
        # H 小时、
        # D 天、
        # W 每星期（interval==0时代表星期一）
        # midnight 每天凌晨
        th.setFormatter(format_str)#设置文件里写入的格式
        self.logger.addHandler(sh) #把对象加到logger里
        self.logger.addHandler(th)

def wrlog():
    filename= getdir()+'/logs/ERR'+time.strftime("%Y%m%d")+'.log'
    log = Logger(filename,level='error')
    log.logger.error(PrintException())
    h1 = log.logger.handlers[0]
    h2 = log.logger.handlers[1]
    log.logger.removeHandler(h1)
    log.logger.removeHandler(h2)
def wdlog(amsg):
    afilename = getdir()+'/logs/DeBug' + time.strftime("%Y%m%d") + '.log'
    log = Logger(afilename,level='debug')
    log.logger.debug(amsg)
    h1 = log.logger.handlers[0]
    h2 = log.logger.handlers[1]
    log.logger.removeHandler(h1)
    log.logger.removeHandler(h2)
