# The MIT License
#
# Copyright (c) 2023 Kensuke Matsuzaki
# Copyright (c) 2026 Hellwig Geisse
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


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
        maxBytes=10000,
        backupCount=3,
    )
    fileHandler.setLevel(logging.INFO)
    fileHandler.setFormatter(simpleFormatter)
    rootLogger.addHandler(fileHandler)


def getLogger(name: str) -> logging.Logger:
    return logging.getLogger(name)
