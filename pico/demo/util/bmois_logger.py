import logging


class CustomFormatter(logging.Formatter):
    debug = "\33[90m[Debug]\x1b[0m "
    warn = "\x1B[33m[Warning]\x1b[0m "
    error = "\x1B[31m[Error]\x1b[0m "
    critical = "\x1b[31;1m[CRITICAL]\x1b[0m "
    # format = "%(asctime)s - %(message)s (%(filename)s:%(lineno)d)"
    format = "%(asctime)s | %(message)s"

    FORMATS = {
        logging.DEBUG: debug + format,
        logging.INFO: "\x1B[34m[Info]\033[0m " + format,
        logging.WARNING: warn + format,
        logging.ERROR: error + format,
        logging.CRITICAL: critical + format
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


_bmois_logger = logging.getLogger('bmois logger')
_bmois_logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(CustomFormatter())
_bmois_logger.addHandler(ch)


def formatargs(*args):
    return ' '.join(map(str, args))


class LogWrapper:
    """
    For some reason formatter fails all the time
    """
    logger: logging.Logger

    def set_level(self, level):
        self.logger.setLevel(level)

    def __init__(self, logger):
        self.logger = logger

    def info(self, *args):
        self.logger.info(formatargs(*args))

    def warn(self, *args):
        self.logger.warning(formatargs(*args))

    def error(self, *args):
        self.logger.error(formatargs(*args))

    def crit(self, *args):
        self.logger.critical(formatargs(*args))

    def debug(self, *args):
        self.logger.debug(formatargs(*args))


logger = LogWrapper(_bmois_logger)

if __name__ == '__main__':
    # logger.info("hello")
    logger.info("Hello, this is a versatile,", 2, logging.Logger('e'), 3 ** 3, 'logger.')
