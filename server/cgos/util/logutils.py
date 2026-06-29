#
# logutils.py -- utility functions for logging
#


import logging
import logging.config
import yaml
import os


def config_basic_logging(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    logging.config.dictConfig(config)


def config_file_logging(log_dir, log_name):
    rootLogger = logging.getLogger()
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    simpleFormatter = logging.Formatter(fmt=format)
    log_path = os.path.join(log_dir, log_name)
    fileHandler = logging.handlers.RotatingFileHandler(
        log_path,
        mode='a',
        maxBytes=10*1024*1024,
        backupCount=10,
    )
    fileHandler.setLevel(logging.INFO)
    fileHandler.setFormatter(simpleFormatter)
    rootLogger.addHandler(fileHandler)


def getLogger(name: str) -> logging.Logger:
    return logging.getLogger(name)
