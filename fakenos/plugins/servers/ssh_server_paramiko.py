"""
This module implements an SSH server done using
paramiko as the SSH connection library.
"""

import logging
import io
import threading
import time
import socket

import paramiko
import paramiko.channel
import paramiko.transport

from fakenos.core.servers import TCPServerBase

log = logging.getLogger(__name__)

DEFAULT_SSH_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAnahBtR7uxtHmk5UwlFfpC/zxdxjUKPD8UpNOOtIJwpei7gaZ
+Jgub5GFJtTG6CK+DIZiR4tE9JxMjTEFDCGA3U4C36shHB15Pl3bLx+UxdyFylpc
c7XYp4fpQjhFUoHOAIl5ZaA223kIxi7sFXtM1Gjy6g49u+G5teVfMbeZnks2xjjy
F84qVADFBXCsfjrY5m4R+Wnfups/jP1agOpnOvqHlX/bpvzEZRcwJ0A8CylBZzQP
D1Y4EXy1B4QLyLJKFIMRkWnr0f8rK5Q/obCLTjl+IMmZrkItbfC/hYCy6TDi+Efn
cgGw02L93Mf6QGDNc21BsRELPYMME22MmpLphQIBIwKCAQEAmScbQjtOWr1GY3r7
/dG90SGaG+w70AALDmM2DUEQy6k/MF4vLAGMMd3RzfNE4YDV4EgHszbVRWSiIsHn
pWJf7OyyVZ7s9r2LuO111gFr82iB98V+YcaX8zOSIxIXdLicOwk0GZRSjA8tGErW
tcg8AYqFkulDSMylxqRN2IZ3+NnTROxh4uUFH57roSYoCvzjM2v1Xa+S42BLpBD1
3mLAJD36JhOhMTgYUgHAROx9+YUUUzYk3jpkTGWnAYSumnJXQYphLE9zadXxh94N
HZJdvXajuP5N2M3Q2b4Gbyt2wNFlNcHGA+Zwk8wHIBnY9Sb9Gz0QALsOAwUoRY8T
rCysSwKBgQDPVjFdSgM3jScmFV9fVnx3iNIlM6Ea7+UCrOOCvcGtzDo5vuTPktw7
8abHEFHw7VrtxI3lRQ41rlmK3B//Q7b+ZJ0HdZaRdyCqW1u91tq1tQe7yiJBm0c5
hZ3F0Vr6HAXoBVOux5wUq55jvUJ8dCVYNYfctZducVmOos3toDkSzQKBgQDCqRQ/
GO5AU3nKfuJ+SZvv8/gV1ki8pGmyxkSebUqZSXFx+rQEQ1e6tZvIz/rYftRkXAyL
XfzXX8mU1wEci6O1oSLiUBgnT82PtUxlO3Peg1W/cpKAaIFvvOIvUMRGFbzWhuj7
4p4KJjZWjYkAV2YlZZ8Br23DFFjjCuawX7NhmQKBgHCN4EiV5H09/08wLHWVWYK3
/Qzhg1fEDpsNZZAd3isluTVKXvRXCddl7NJ2kuHf74hjYvjNt0G2ax9+z4qSeUhF
P00xNHraRO7D4VhtUiggcemZnZFUSzx7vAxNFCFfq29TWVBAeU0MtRGSoG9yQCiS
Fo3BqfogRo9Cb8ojxzYXAoGBAIV7QRVS7IPheBXTWXsrKRmRWaiS8AxTe63JyKcm
XwoGea0+MkwQ67M6s/dqCxgcdGITO81Hw1HbSGYPxj91shYlWb/B5K0+CUyZk3id
y8vHxcUbXSTZ8ls/sQqAhpZ1Tkn2HBpvglAaM+OUQK/G5vUSe6liWeTawJuvtCEr
rjRLAoGAUNNY4/7vyYFX6HkX4O2yL/LZiEeR6reI9lrK/rSA0OCg9wvbIpq+0xPG
jCrc8nTlA0K0LtEnE+4g0an76nSWUNiP4kALROfZpXajRRaWdwFRAO17c9T7Uxc0
Eez9wYRqHiuvU0rryYvGyokr62w1MtJO0tttnxe1Of6wzb1WeCU=
-----END RSA PRIVATE KEY-----"""


class ParamikoSshServerInterface(paramiko.ServerInterface):
    """
    Class to implement the SSH server interface
    using paramiko as the SSH connection library.
    """

    def __init__(
        self,
        ssh_banner="FakeNOS Paramiko SSH Server",
        username=None,
        password=None,
    ):
        self.ssh_banner = ssh_banner
        self.username = username
        self.password = password

    def check_channel_request(self, kind, chanid):
        """
        This will allow the SSH server to provide a channel for the client
        to communicate over. By default, this will return
        OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED, so  we have to override it
        to return OPEN_SUCCEEDED when the kind of channel
        requested is "session".
        """
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    # pylint: disable=too-many-arguments
    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        """
        AFAIK, pty (pseudo-tty (TeleTYpewriter))
        will allow our client to interact with our shell.
        """
        return True

    def check_channel_shell_request(self, channel):
        """
        This allows us to provide the channel
        with a shell we can connect to it.
        """
        return True

    def check_auth_password(self, username, password):
        if (username == self.username) and (password == self.password):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_banner(self):
        """
        String that will display when a client connects,
        before authentication has happened. This is different
        than the shell's intro property, which is displayed
        after the authentication.
        """
        return (self.ssh_banner + "\r\n", "en-US")


class TapIO(io.StringIO):
    """
    Class to implement StringIO subclass but with blocking readline method
    and a list to buffer lines on write
    """

    def __init__(self, run_srv, initial_value="", newline="\n"):
        self.lines = []
        self.run_srv = run_srv
        super().__init__(initial_value, newline)

    def readline(self):
        """method to readline in indefinite block mode"""
        while self.run_srv.is_set():
            if self.lines:
                return self.lines.pop(-1)
            time.sleep(0.01)
        return None

    def write(self, value):
        """
        :param value: line to add to self.lines buffer
        """
        self.lines.insert(0, value)


def channel_to_shell_tap(channel_stdio, shell_stdin, shell_replied_event, run_srv):
    """
    Method to tap into the channel_stdio and send it to the shell
    """
    buffer = io.BytesIO()
    while run_srv.is_set():
        byte = channel_stdio.read(1)
        log.debug("ssh_server.channel_to_shell_tap received from channel: %s", [byte])
        if byte in (b"\r", b"\n"):
            shell_replied_event.wait(10)
            if not channel_stdio.channel.active:
                log.error("SSH channel is not active. Exiting.")
                break
            log.debug("ssh_server.channel_to_shell_tap echoing new line to channel: %s", [b"\r\n"])
            try:
                channel_stdio.write(b"\r\n")
            except (OSError, EOFError) as e:
                log.error("ssh_server.channel_to_shell_tap channel write error: %s", e)
                break
            buffer.write(byte)
            buffer.seek(0)
            line = buffer.read().decode(encoding="utf-8")
            buffer.seek(0)
            buffer.truncate()
            log.debug("ssh_server.channel_to_shell_tap sending line to shell: %s", [line])
            shell_stdin.write(line)
            shell_replied_event.clear()
        else:
            shell_replied_event.wait(10)
            if not channel_stdio.channel.active:
                log.error("SSH channel is not active. Exiting.")
                break
            try:
                channel_stdio.write(byte)
            except (OSError, EOFError) as e:
                log.error("ssh_server.channel_to_shell_tap channel write error: %s", e)
                break
            if byte not in [b"\x00", b""]:
                buffer.write(byte)
        time.sleep(0.01)


def shell_to_channel_tap(
    channel_stdio: paramiko.channel.ChannelFile,
    shell_stdout: TapIO,
    shell_replied_event: threading.Event,
    run_srv: threading.Event,
):
    """
    Method to tap into the shell_stdout and send it to the channel
    """
    while run_srv.is_set():
        if channel_stdio.closed:
            break
        line = shell_stdout.readline()
        # line is None we break the loop
        if line is None:
            break
        if "\r\n" not in line and "\n" in line:
            line = line.replace("\n", "\r\n")
        log.debug("ssh_server.shell_to_channel_tap sending line to channel %s", [line])
        try:
            channel_stdio.write(line.encode(encoding="utf-8"))
        except socket.error as e:
            if e.errno == 104:  # Connection reset by peer
                log.error("ssh_server.shell_to_channel_tap channel write error: %s", e)
                break
        shell_replied_event.set()


class ParamikoSshServer(TCPServerBase):
    """
    Class to implement an SSH server using paramiko
    as the SSH connection library.
    """

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        shell,
        nos,
        nos_inventory_config,
        port,
        username,
        password,
        ssh_key_file=None,
        ssh_key_file_password=None,
        ssh_banner="FakeNOS Paramiko SSH Server",
        shell_configuration=None,
        address="127.0.0.1",
        timeout=1,
        watchdog_interval=1,
    ):
        super().__init__()

        self.nos = nos
        self.nos_inventory_config = nos_inventory_config
        self.shell = shell
        self.shell_configuration = shell_configuration or {}
        self.ssh_banner = ssh_banner
        self.username = username
        self.password = password
        self.port = port
        self.address = address
        self.timeout = timeout
        self.watchdog_interval = watchdog_interval

        if ssh_key_file:
            self._ssh_server_key = paramiko.RSAKey.from_private_key_file(ssh_key_file, ssh_key_file_password)
        else:
            self._ssh_server_key = paramiko.RSAKey(file_obj=io.StringIO(DEFAULT_SSH_KEY))

    def watchdog(self, is_running, run_srv, session, shell):
        """
        Method to monitor server liveness and recover where possible.
        """
        while run_srv.is_set():
            # check if session is alive, stop shell if it is not
            if not session.is_alive():
                log.warning(
                    "ParamikoSshServer.watchdog - \
                        session not alive, stopping shell"
                )
                shell.stop()
                break
            
            # exit the shell
            if not is_running.is_set():
                shell.stop()

            time.sleep(self.watchdog_interval)

    def connection_function(self, client, is_running):
        shell_replied_event = threading.Event()
        run_srv = threading.Event()
        run_srv.set()

        # create the SSH transport object
        session = paramiko.Transport(client)
        session.add_server_key(self._ssh_server_key)

        # create the server
        server = ParamikoSshServerInterface(
            ssh_banner=self.ssh_banner,
            username=self.username,
            password=self.password,
        )

        # start the SSH server
        session.start_server(server=server)

        # create the channel and get the stdio
        channel = session.accept()
        channel_stdio = channel.makefile("rw")

        # create stdio for the shell
        shell_stdin, shell_stdout = TapIO(run_srv), TapIO(run_srv)

        # start intermediate thread to tap into
        # the channel_stdio->shell_stdin bytes stream
        channel_to_shell_tapper = threading.Thread(
            target=channel_to_shell_tap,
            args=(channel_stdio, shell_stdin, shell_replied_event, run_srv),
        )
        channel_to_shell_tapper.start()

        # start intermediate thread to tap into
        # the shell_stdout->channel_stdio bytes stream
        shell_to_channel_tapper = threading.Thread(
            target=shell_to_channel_tap,
            args=(channel_stdio, shell_stdout, shell_replied_event, run_srv),
        )
        shell_to_channel_tapper.start()

        # create the client shell
        client_shell = self.shell(
            stdin=shell_stdin,
            stdout=shell_stdout,
            nos=self.nos,
            nos_inventory_config=self.nos_inventory_config,
            is_running=is_running,
            **self.shell_configuration,
        )

        # start watchdog thread
        watchdog_thread = threading.Thread(target=self.watchdog, args=(is_running, run_srv, session, client_shell))
        watchdog_thread.start()

        # running this command will block this function until shell exits
        client_shell.start()
        log.debug("ParamikoSshServer.connection_function stopped shell thread")

        # kill this server threads - watchdog, TapIO,
        # shell_to_channel_tapper and channel_to_shell_tapper
        run_srv.clear()
        log.debug("ParamikoSshServer.connection_function stopped server threads")

        # After execution continues, we can close the session
        session.close()
        log.debug("ParamikoSshServer.connection_function closed transport %s", session)
