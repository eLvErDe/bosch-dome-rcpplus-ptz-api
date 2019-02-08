""" aiohttp middlewares """
import logging
import asyncio
import functools
import aiohttp


from services import RcpHttpException


@asyncio.coroutine
def rest_error_middleware(_, handler, logger=None):
    """
    A middleware to return rest JSON error when something goes wrong
    Also turn AssertionError into 400 bad request
    """

    @asyncio.coroutine
    def return_rest_error_response(request, logger=None):
        """ middleware handler """

        try:
            response = yield from handler(request)

        except Exception as exc:  # pylint: disable=broad-except

            # Log exception if have a logger
            if isinstance(logger, logging.Logger):
                logger.exception("Error handling request: %s: %s", exc.__class__.__name__, exc)

            # Define status code according to exception type
            if isinstance(exc, aiohttp.web.HTTPException):
                status = exc.status  # pylint: disable=no-member
                message = exc.reason  # pylint: disable=no-member
            elif isinstance(exc, RcpHttpException):
                status = exc.status_code  # pylint: disable=no-member
                message = exc.message  # pylint: disable=no-member
            elif isinstance(exc, AssertionError):
                status = 400
                message = str(exc)
            else:
                status = 500
                message = "Internal Server Error"

            rest_error = {"message": message, "status": status}

            response = aiohttp.web.json_response(rest_error, status=status)

        finally:
            return response  # pylint: disable=lost-exception

    return functools.partial(return_rest_error_response, logger=logger)
