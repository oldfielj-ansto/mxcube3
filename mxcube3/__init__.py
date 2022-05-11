import sys
import mock
import os

from gevent import monkey

# NB HardwareRepository must be imported *before* the gevent monkeypatching
# in order to set the unpatched version of socket for use elseqhere
# See HardwareRepository.original_socket
from mxcubecore import HardwareRepository as HWR

monkey.patch_all(thread=False)


from optparse import OptionParser

from mxcube3.config import Config
from mxcube3.app import MXCUBEApplication
from mxcube3.server import Server

sys.modules["Qub"] = mock.Mock()
sys.modules["Qub.CTools"] = mock.Mock()

mxcube = MXCUBEApplication()
server = Server()


def parse_args():
    XML_DIR = os.path.join(
        os.path.join(os.path.dirname(__file__), os.pardir),
        "test/HardwareObjectsMockup.xml/",
    )

    opt_parser = OptionParser()

    opt_parser.add_option(
        "-r",
        "--repository",
        dest="hwr_directory",
        help="Hardware Repository XML files path",
        default=XML_DIR,
    )

    opt_parser.add_option(
        "-s",
        "--static-folder",
        dest="static_folder",
        help="Static folder",
        default=f"{os.getcwd()}ui/build",
    )

    opt_parser.add_option(
        "-l",
        "--log-file",
        dest="log_file",
        help="Log file name",
        default="",
    )

    opt_parser.add_option(
        "-L",
        "--log-level",
        dest="log_level",
        help="Log level for thirdparty libraries, mxcube-server log level is always DEBUG ",
        default="",
    )

    opt_parser.add_option(
        "-d",
        "--video-device",
        dest="video_device",
        help="Video device, defaults to: No device",
        default="",
    )

    opt_parser.add_option(
        "-w",
        "--ra",
        action="store_true",
        dest="allow_remote",
        help="Enable remote access",
        default=False,
    )

    opt_parser.add_option(
        "-t",
        "--ra-timeout",
        action="store_true",
        dest="ra_timeout",
        help="Timeout gives control",
        default=False,
    )

    return opt_parser.parse_args()


def main():
    cmdline_options, args = parse_args()

    # This refactoring (with other bits) allows you to pass a 'path1:path2' lookup path
    # as the hwr_directory. I need it for sensible managing of a multi-beamline test set-up
    # without continuously editing teh main config files.
    # Note that the machinery was all there in the core alrady. rhfogh.
    HWR.init_hardware_repository(cmdline_options.hwr_directory)
    config_path = HWR.get_hardware_repository().find_in_repository(
        "mxcube-web"
    )

    cfg = Config(config_path)

    server.init(cmdline_options, cfg, mxcube)

    mxcube.init(
        server,
        cmdline_options.allow_remote,
        cmdline_options.ra_timeout,
        cmdline_options.video_device,
        cmdline_options.log_file,
        cmdline_options.log_level,
        cfg,
    )

    server.register_routes(mxcube)

    server.run()


if __name__ == "__main__":
    main()
