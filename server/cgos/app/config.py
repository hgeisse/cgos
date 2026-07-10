#
# config.py -- configure the CGOS server and web page builder
#


import yaml
import sys
import os
from enum import Enum
from typing import Optional

from gogame import KoRule
from util.logutils import getLogger
from util.logutils import config_basic_logging
from util.logutils import config_file_logging


# Setup logger
logger = getLogger("cgos_server.client")


class MatchMode(Enum):
    AUTO = 0
    ADMIN = 1


class Configs:
    serverName: str
    boardsize: int
    komi: float
    koRule: KoRule
    level: int
    portNumber: int
    timeGift: float
    logging_directory: str
    logging_filename: str
    database_state_file: str
    game_archive_database: Optional[str]
    web_data_file: str
    defaultRating: float
    minK: float
    maxK: float
    htmlDir: str
    htmlInfoMsg: str
    sgfDir: str
    compressSgf: bool
    provisionalAge: float
    establishedAge: float
    killFileSrv: str
    killFileWeb: str
    anchor_trigger_file: str
    anchor_ratings_file: str
    anchor_match_rate: float
    badUsersFile: str
    moves_per_save: int
    hashPassword: bool
    matchMode: MatchMode

    def load(self, path: str, enable_file_logging: bool) -> None:
        # install basic logging in any case
        config_basic_logging('configs/logging/log.yaml')

        # read CGOS configuration
        with open(path, 'r') as f:
            cfg = yaml.safe_load(f)

        # if file logging is enabled, install it
        if enable_file_logging:
            # create logging directory and configure logging to a file
            self.logging_directory = str(cfg["logging_directory"])
            self.logging_filename = str(cfg["logging_filename"])
            try:
                os.makedirs(self.logging_directory, exist_ok=True)
            except Exception as e:
                logger.error("Error creating logging directory", e, str(e))
                sys.exit(1)
            config_file_logging(self.logging_directory, self.logging_filename)

        self.serverName = str(cfg["serverName"])
        self.portNumber = int(cfg["portNumber"])
        self.boardsize = int(cfg["boardsize"])
        self.komi = float(cfg["komi"])
        if "koRule" in cfg:
            try:
                self.koRule = KoRule[cfg["koRule"]]
            except:
                logger.error(f'Bad ko rule {cfg["koRule"]}')
                sys.exit(1)
        else:
            self.koRule = KoRule.POSITIONAL

        self.level = int(cfg["level"]) * 1000
        self.timeGift = float(cfg["timeGift"])
        self.database_state_file = str(cfg["database_state_file"])
        if "game_archive_database" in cfg:
            self.game_archive_database = str(cfg["game_archive_database"])
        else:
            self.game_archive_database = None
        self.web_data_file = str(cfg["web_data_file"])
        self.defaultRating = float(cfg["defaultRating"])
        self.minK = float(cfg["minK"])
        self.maxK = float(cfg["maxK"])
        self.htmlDir = str(cfg["htmlDir"])
        self.htmlInfoMsg = str(cfg["htmlInfoMsg"])
        self.sgfDir = str(cfg["sgfDir"])
        if "compressSgf" in cfg:
            self.compressSgf = bool(cfg["compressSgf"])
        else:
            self.compressSgf = False
        self.provisionalAge = float(cfg["provisionalAge"])
        self.establishedAge = float(cfg["establishedAge"])
        self.killFileSrv = str(cfg["killFileSrv"])
        self.killFileWeb = str(cfg["killFileWeb"])
        self.anchor_trigger_file = str(cfg["anchor_trigger_file"])
        self.anchor_ratings_file = str(cfg["anchor_ratings_file"])
        if "anchor_match_rate" in cfg:
            self.anchor_match_rate = float(cfg["anchor_match_rate"])
        else:
            self.anchor_match_rate = 0.10
        if "bad_users_file" in cfg:
            self.badUsersFile = str(cfg["bad_users_file"])
        else:
            self.badUsersFile = None
        if "moves_per_save" in cfg:
            self.moves_per_save = int(cfg["moves_per_save"])
        else:
            self.moves_per_save = 1
        if "hashPassword" in cfg:
            self.hashPassword = bool(cfg["hashPassword"])
        else:
            self.hashPassword = False

        self.matchMode = MatchMode.AUTO
        if "matchMode" in cfg:
            try:
                self.matchMode = MatchMode[cfg["matchMode"]]
            except:
                logger.error(f"Bad match mode {cfg['matchMode']}")
                sys.exit(1)
