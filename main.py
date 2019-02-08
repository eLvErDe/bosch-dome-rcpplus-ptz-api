#!/usr/bin/python3


# pylint: disable=line-too-long


"""
Main file to run auth_server either standalone
or using gunicorn by returning app object
"""


import sys
import os
import shutil
import logging
import argparse
import configparser
import aiohttp.web
import setproctitle

from api_factory import ApiFactory


PROJECT_ROOT = os.path.abspath(os.path.join(__file__, os.pardir))


def set_process_name(config_obj=None):
    """ Set process name according to pom.xml file """

    artifact_id = "rcp-ptz-api"
    version = "1.0"

    # Strip passwords from arguments
    cli_args = " ".join(sys.argv[1:])
    if isinstance(config_obj, argparse.Namespace):
        for key, val in config_obj.__dict__.items():
            if isinstance(val, str) and key.lower().endswith(("pass", "password", "passwd", "key")):
                cli_args = cli_args.replace(val, "<hidden>")

    setproctitle.setproctitle("%s-%s %s" % (artifact_id, version, cli_args))  # pylint: disable=maybe-no-member,c-extension-no-member


def configure_root_logger(level=logging.INFO):
    """ Override root logger to use a better formatter """

    if os.getenv("NO_LOGS_TS", None) is None:
        formatter = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    else:
        formatter = "%(levelname)-8s [%(name)s] %(message)s"

    logging.basicConfig(level=level, format=formatter, stream=sys.stdout)


def get_arguments_from_cmd_line():
    """ Handle command line arguments """
    # pylint: disable=bad-whitespace

    # Raise terminal size, See https://bugs.python.org/issue13041
    os.environ["COLUMNS"] = str(shutil.get_terminal_size().columns)

    parser = argparse.ArgumentParser(
        description="API to download Sentinel/Landsat satellite product files", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("-b", "--bind-address", type=str, default="::1", help="Address to bind on", metavar="0.0.0.0")
    parser.add_argument("-p", "--bind-port", type=int, default=5000, help="Port to bind on", metavar=8877)

    parser.add_argument("-c", "--context-path", type=str, default="/", help="Text to be used as prefix URL")
    parser.add_argument("-d", "--debug", action="store_true", help="Put loggers in DEBUG level")
    parser.add_argument("-o", "--allow-origin", type=str, help="Allow to restrict the API access to the given URL or domain only")

    parser.add_argument(
        "-f", "--config-file", type=str, default=os.path.join(PROJECT_ROOT, "config.ini"), help="Path to INI configuration file defining cameras"
    )

    parsed = parser.parse_args()
    if parsed.context_path != "/":
        parsed.context_path = "/" + parsed.context_path.strip("/") + "/"

    parsed.cams = parse_ini_config(parsed.config_file)
    parsed.PROJECT_ROOT = PROJECT_ROOT

    return parsed


def parse_ini_config(filepath):
    """
    Parse INI file containing cameras definitions
    """

    parser = configparser.ConfigParser()
    parser.read(filepath)

    cams = {}
    for cam in parser.sections():
        cams[cam] = {
            "url": parser.get(cam, "url"),
            "username": parser.get(cam, "username", fallback=None),
            "password": parser.get(cam, "password", fallback=None),
        }

    return cams


def create_api():
    """ Setup app for both command line and Gunicorn run """

    config = get_arguments_from_cmd_line()
    log_level = logging.DEBUG if config.debug else logging.INFO
    configure_root_logger(level=log_level)
    set_process_name(config_obj=config)
    return ApiFactory(config=config)


if __name__ == "__main__":

    API = create_api()
    aiohttp.web.run_app(
        API.app, host=API.config.bind_address, port=API.config.bind_port, access_log_format="%s %r [status:%s request:%Tfs bytes:%bb]"
    )
