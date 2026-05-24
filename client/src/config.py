#
# config.py -- read and validate a client configuration
#


import yaml


COMMON_NAME = 'Common'
COMMON_REQUIRED_KEYS = [
    "KillFile",
]
COMMON_OPTIONAL_KEYS = [
    "LogFile",
]


ENGINES_NAME = 'Engines'
ENGINE_REQUIRED_KEYS = [
    "EngineName",
    "CommandLine",
    "ServerHost",
    "ServerPort",
    "ServerUser",
    "ServerPassword",
]
ENGINE_OPTIONAL_KEYS = [
    "NumberOfGames",
    "GenmoveDelay",
    "SGFDirectory",
    "EngineLogFile",
]


def validate(config):
    hasCommon = False
    hasEngine = False
    for section_name in config.keys():
        if section_name == COMMON_NAME:
            common = config[section_name]
            # detect missing required attributes
            for required_key in COMMON_REQUIRED_KEYS:
                if not (required_key in common.keys()):
                    # this is an error
                    raise Exception(
                        f"Mandatory common attribute " +
                        f"'{required_key}' missing"
                    )
            # detect missing optional attributes
            for optional_key in COMMON_OPTIONAL_KEYS:
                if not (optional_key in common.keys()):
                    # not an error, but must set default value
                    common[optional_key] = None
            # detect unknown attributes
            for key in common.keys():
                if key not in COMMON_REQUIRED_KEYS:
                    if key not in COMMON_OPTIONAL_KEYS:
                        raise Exception(
                            f"Unknown attribute '{key}' " +
                            f"in section '{COMMON_NAME}'"
                        )
            hasCommon = True
        elif section_name == ENGINES_NAME:
            engines = config[section_name]
            if type(engines) != list:
                raise Exception(
                    "The 'Engines' section is not a list (of engines)"
                )
            # iterate over engines
            for (index, engine) in enumerate(engines):
                # detect missing required attributes
                for required_key in ENGINE_REQUIRED_KEYS:
                    if not (required_key in engine.keys()):
                        # this is an error
                        raise Exception(
                            f"Mandatory engine attribute " +
                            f"'{required_key}' missing"
                        )
                # detect missing optional attributes
                for optional_key in ENGINE_OPTIONAL_KEYS:
                    if not (optional_key in engine.keys()):
                        # not an error, but must set default value
                        engine[optional_key] = None
                # detect unknown attributes
                for key in engine.keys():
                    if key not in ENGINE_REQUIRED_KEYS:
                        if key not in ENGINE_OPTIONAL_KEYS:
                            raise Exception(
                                f"Unknown attribute '{key}' " +
                                f"in engine {index}"
                            )
            if len(engines) > 0:
                hasEngine = True
        else:
            raise Exception(
                f"Unknown section '{section_name}' in configuration"
            )
    if not hasCommon:
        raise Exception(
            "A common section must be defined in configuration"
        )
    if not hasEngine:
        raise Exception(
            "At least one engine must be defined in configuration"
        )


def load_config(fileName):
    with open(fileName, 'r') as f:
        config = yaml.safe_load(f)
    validate(config)
    return config
