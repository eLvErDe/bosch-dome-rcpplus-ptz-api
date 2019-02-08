"""
aiohttp asynchronous Bsoch RCP+ client
For dome camera PTZ handling
"""


# pylint: disable=line-too-long


import logging
import asyncio
import aiohttp


class RcpException(Exception):
    """
    Base class for all errors while communicating with RCP protocol
    """

    pass


class RcpHttpException(RcpException):
    """
    HTTP worked but got unexpected status code
    :param message: Exception message
    :param exception: Name of the exception
    :param status_code: HTTP status code
    :type status_code: int
    """

    _expected_status_codes = []

    def __init__(self, message, text, status_code):
        if self._expected_status_codes:
            assert status_code in self._expected_status_codes, "Got HTTP/%d while %s expected" % (status_code, self._expected_status_codes)
        self.message = "%s: %s" % (message, text)
        super(RcpHttpException, self).__init__(self.message)
        self.status_code = status_code


class RcpHttpUnauthorizedException(RcpHttpException):  # pylint: disable=missing-docstring
    _expected_status_codes = [401]


class RcpHttpForbiddenException(RcpHttpException):  # pylint: disable=missing-docstring
    _expected_status_codes = [403]


class RcpHttpNotFoundException(RcpHttpException):  # pylint: disable=missing-docstring
    _expected_status_codes = [404]


class RcpHttpInternalServerErrorException(RcpHttpException):  # pylint: disable=missing-docstring
    _expected_status_codes = [500, 502, 503, 504]


@asyncio.coroutine
def _check_response(response, expected_status=200):
    if response.status == expected_status:
        return response

    try:
        text = yield from response.text()
        text = text.strip()
    except:  # pylint: disable=bare-except
        text = ""

    if response.status == 401:
        cls = RcpHttpUnauthorizedException
        message = "401 Unauthorized"
    elif response.status == 403:
        cls = RcpHttpForbiddenException
        message = "403 HttpForbidden"
    elif response.status == 404:
        cls = RcpHttpNotFoundException
        message = "404 Not Found"
    elif response.status in [500, 502, 503, 504]:
        cls = RcpHttpInternalServerErrorException
        if response.status == 500:
            message = "500 Internal Server Error"
        elif response.status == 502:
            message = "502 Bad Gateway"
        elif response.status == 503:
            message = "503 Service Unavailable"
        elif response.status == 504:
            message = "504 Gateway Timeout"
        else:
            message = "Uh? Some unhandled server side error"
    else:
        cls = RcpHttpException
        message = "%d Unhandled exception" % response.status
    raise cls(message=message, text=text, status_code=response.status) from None


class AsyncRcpClient(object):  # pylint: disable=too-many-instance-attributes
    """ aiohttp asynchronous RCP client """

    BITCOM_ID = "0x800006011085"
    PTZ_SPEED_MIN = 0
    PTZ_SPEED_MAX = 7

    def __init__(  # pylint: disable=too-many-arguments
        self, url="http://localhost", timeout=1, session=None, username=None, password=None, name="Unspecified"  # pylint: disable=bad-continuation
    ):

        assert isinstance(url, str) and str, "url must be a non-empty string"
        assert isinstance(timeout, int) and timeout > 0, "timeout must be a integer (seconds)"
        if session is not None:
            assert isinstance(session, aiohttp.ClientSession), "session must be a aiohttp.ClientSession instance or None"
        if username is not None:
            assert isinstance(username, str) and str, "username must be a non-empty string or None"
            assert password is not None, "username and password must be specified or none of them"
        if password is not None:
            assert isinstance(password, str) and str, "password must be a non-empty string or None"
            assert username is not None, "username and password must be specified or none of them"
        assert isinstance(name, str) and name, "name must be a non-empty string"

        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session = session
        self.ext_session = True
        if self.session is None:
            self.ext_session = False
            self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10))
        self.username = username
        self.password = password
        self.auth = None
        if self.username is not None:
            self.auth = aiohttp.helpers.BasicAuth(self.username, self.password)
        self.name = name
        self.logger = logging.getLogger(self.__class__.__name__ + "@" + self.name)
        self.logger.info("Initialized at %s", self.url)

    @asyncio.coroutine
    def close(self):
        """ Kill asyncio session on shutdown """

        if not self.ext_session:
            yield from self.session.close()
        self.logger.info("Stopped")

    @asyncio.coroutine
    def _request(self, method, path, expected_status=200, params=None):
        """ Perform actual HTTP request """

        path = "/" + path.lstrip("/")
        try:
            response = yield from self.session.request(method, self.url + path, timeout=self.timeout, params=params, auth=self.auth)
        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            raise RcpException("%s: %s" % (exc.__class__.__name__, exc)) from None

        yield from _check_response(response, expected_status)

    @asyncio.coroutine
    def move_ptz(  # pylint: disable=too-many-arguments,invalid-name,too-many-branches,too-many-statements
        self, left=0, right=0, up=0, down=0, zin=0, zout=0, stop=False  # pylint: disable=bad-continuation
    ):
        """ Call RCP+ and request for PTZ move """

        if isinstance(left, str) and left.isdigit():
            left = int(left)
            assert (
                isinstance(left, int) and left <= self.PTZ_SPEED_MAX and left >= self.PTZ_SPEED_MIN
            ), "PTZ speed (left axis) must be between 0 and 7 (int)"
        if isinstance(right, str) and right.isdigit():
            right = int(right)
            assert (
                isinstance(right, int) and right <= self.PTZ_SPEED_MAX and right >= self.PTZ_SPEED_MIN
            ), "PTZ speed (right axis) must be between 0 and 7 (int)"
        if isinstance(up, str) and up.isdigit():
            up = int(up)
            assert isinstance(up, int) and up <= self.PTZ_SPEED_MAX and up >= self.PTZ_SPEED_MIN, "PTZ speed (up axis) must be between 0 and 7 (int)"
        if isinstance(down, str) and down.isdigit():
            down = int(down)
            assert (
                isinstance(down, int) and down <= self.PTZ_SPEED_MAX and down >= self.PTZ_SPEED_MIN
            ), "PTZ speed (down axis) must be between 0 and 7 (int)"
        if isinstance(zin, str) and zin.isdigit():
            zin = int(zin)
            assert (
                isinstance(zin, int) and zin <= self.PTZ_SPEED_MAX and zin >= self.PTZ_SPEED_MIN
            ), "PTZ speed (zin axis) must be between 0 and 7 (int)"
        if isinstance(zout, str) and zout.isdigit():
            zout = int(zout)
            assert (
                isinstance(zout, int) and zout <= self.PTZ_SPEED_MAX and zout >= self.PTZ_SPEED_MIN
            ), "PTZ speed (zout axis) must be between 0 and 7 (int)"
        if isinstance(stop, str) and stop.isdigit():
            stop = int(stop)
        assert stop in [0, 1, True, False], "Stop must be either True or False"
        stop = bool(stop)

        if stop:
            assert not any([left, right, up, down, zin, zout]), "All axis must be 0 when stop=True"  # pylint: disable=multiple-statements
        if left:
            assert not right, "left and right move are exclusive"  # pylint: disable=multiple-statements
        if right:
            assert not left, "left and right move are exclusive"  # pylint: disable=multiple-statements
        if up:
            assert not down, "up and down move are exclusive"  # pylint: disable=multiple-statements
        if down:
            assert not up, "up and down move are exclusive"  # pylint: disable=multiple-statements
        if zin:
            assert not zout, "zin and zout move are exclusive"  # pylint: disable=multiple-statements
        if zout:
            assert not zin, "zin and zout move are exclusive"  # pylint: disable=multiple-statements

        self.logger.info("Moving: left=%s, right=%s, up=%s, down=%s, in=%s, out=%s, stop=%s", left, right, up, down, zin, zout, stop)

        action_r = [0, 0, 0, 0, 0, 0]
        if left:
            action_r[0] = 0
            action_r[1] = left
        else:
            action_r[0] = 8
            action_r[1] = right
        if up:
            action_r[2] = 8
            action_r[3] = up
        else:
            action_r[2] = 0
            action_r[3] = down
        if zin:
            action_r[4] = 8
            action_r[5] = zin
        else:
            action_r[4] = 0
            action_r[5] = zout

        if stop:
            action = "000000"
        else:
            action = "".join([str(x) for x in action_r])

        payload = self.BITCOM_ID + action

        rcp_path = "/rcp.xml"
        rcp_params = {"command": "0x09A5", "type": "P_OCTET", "direction": "WRITE", "num": 1, "payload": payload}

        response = yield from self._request("GET", rcp_path, params=rcp_params)
        return response


if __name__ == "__main__":

    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s", stream=sys.stdout)
    LOGGER = logging.getLogger(__name__)
    logging.getLogger("timeit").setLevel(logging.DEBUG)

    @asyncio.coroutine
    def test_ptz():
        """ Run RCP+ queries to test this service """

        client = AsyncRcpClient(url="http://127.0.0.1", username="username", password="password", name="ExampleCam")

        try:
            yield from client.move_ptz(left=2, up=2)
            yield from asyncio.sleep(2)
            yield from client.move_ptz(right=2, down=2)
            yield from asyncio.sleep(2)
            yield from client.move_ptz(stop=True)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("%s: %s", exc.__class__.__name__, exc)
        finally:
            yield from client.close()

    LOOP = asyncio.get_event_loop()
    TASK = asyncio.ensure_future(test_ptz())
    try:
        LOOP.run_until_complete(TASK)
    except KeyboardInterrupt:
        LOOP.run_until_complete(TASK)
    finally:
        LOOP.close()
