""" Run PTZ action using query params """


# pylint: disable=line-too-long


import logging
import asyncio
import string
import random
import aiohttp.web


class PtzMove(object):  # pylint: disable=too-few-public-methods
    """ Run PTZ action using query params """

    def __init__(self, cam_id, auto_release_delay=10):
        self.logger = logging.getLogger(self.__class__.__name__ + "@" + cam_id)
        self.cam_id = cam_id
        self.auto_release_delay = auto_release_delay
        self.locked = False
        self.delayed_unlock_coro = None

    def _lock(self):
        """
        Lock this camera PTZ and return token
        to bypass lock
        """

        token = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        self.locked = token

        self.delayed_unlock_coro = asyncio.ensure_future(self._delayed_unlock())

        return token

    def _renew_lock(self):
        """
        Cancel auto-release-lock coroutine
        and start a new one
        """

        if self.delayed_unlock_coro:
            self.delayed_unlock_coro.cancel()
        self.delayed_unlock_coro = asyncio.ensure_future(self._delayed_unlock())

    def _unlock(self):
        """
        Cancel auto-release-lock coroutine
        and mark PTZ as free
        """

        if self.delayed_unlock_coro:
            self.delayed_unlock_coro.cancel()
        self.locked = False

    @asyncio.coroutine
    def _delayed_unlock(self):
        """
        Schedule automatic lock release
        after seconds for recovery of unclean
        leave (without calling with stop=1)
        """

        yield from asyncio.sleep(self.auto_release_delay)
        self._unlock()
        self.logger.info("PTZ lock released after %d seconds of inactivity", self.auto_release_delay)

    @asyncio.coroutine
    def get(self, request):
        """
        ---
        description: Run PTZ moves on camera
        produces:
        - application/json
        tags:
        - ptz
        parameters:
        - in: query
          name: left
          description: Move left at given speed
          required: False
          type: integer
          minimum: 0
          maximum: 7
        - in: query
          name: right
          description: Move right at given speed
          required: False
          type: integer
          minimum: 0
          maximum: 7
        - in: query
          name: up
          description: Move up at given speed
          required: False
          type: integer
          minimum: 0
          maximum: 7
        - in: query
          name: down
          description: Move down at given speed
          required: False
          type: integer
          minimum: 0
          maximum: 7
        - in: query
          name: zin
          description: Zoom in at given speed
          required: False
          type: integer
          minimum: 0
          maximum: 7
        - in: query
          name: zout
          description: Zoom out at given speed
          required: False
          type: integer
          minimum: 0
          maximum: 7
        - in: query
          name: stop
          description: Stop moving
          required: False
          type: integer
          minimum: 0
          maximum: 1
        - in: query
          name: lock_token
          description: Token to keep PTZ locked (Will be returned with first request if PTZ is not already used). Token is cleared if after NNs inactivity or NNs after stop=1.
          required: False
          type: string
          example: gua7Aim4
        responses:
            200:
                description: PTZ move applied
                schema:
                    title: Success
                    type: object
                    required:
                        - status
                        - message
                        - lock_token
                    properties:
                        message:
                            type: string
                            description: Success message
                            example: PTZ move applied
                        status:
                            type: number
                            description: HTTP success status code
                            example: 200
                        lock_token:
                            type: string
                            description: Token to keep PTZ locked, pass it to next calls
                            example: gua7Aim4
            400:
                description: Bad request
                schema:
                    title: Bad_Request
                    type: object
                    required:
                        - status
                        - message
                    properties:
                        message:
                            type: string
                            description: Validation error message
                            example: left and right move are exclusive
                        status:
                            type: number
                            description: HTTP error status code
                            example: 400
            401:
                description: Authentication failed
                schema:
                    title: Authentication_Error
                    type: object
                    required:
                        - status
                        - message
                    properties:
                        message:
                            type: string
                            description: Authentication error message
                            example: Authentication failed
                        status:
                            type: number
                            description: HTTP error status code
                            example: 401
            403:
                description: Forbidden
                schema:
                    title: Forbidden
                    type: object
                    required:
                        - status
                        - message
                    properties:
                        message:
                            type: string
                            description: Forbidden error message
                            example: PTZ is already in use
                        status:
                            type: number
                            description: HTTP error status code
                            example: 403
        """

        # Extract query params
        args = {}
        for key in ["left", "right", "up", "down", "zin", "zout", "stop"]:
            args[key] = request.rel_url.query.get(key, 0)
        lock_token = request.rel_url.query.get("lock_token", None)

        # Parse stop query param to be able to release camera lock on stop request
        if isinstance(args["stop"], str) and args["stop"].isdigit():
            args["stop"] = int(args["stop"])
        assert args["stop"] in [0, 1, True, False], "Stop must be either True or False"
        args["stop"] = bool(args["stop"])

        # Verify lock state
        if self.locked:
            if self.locked != lock_token:
                payload = {"message": "PTZ is already in use", "status": 403}
                return aiohttp.web.json_response(payload, status=403)
            else:
                self._renew_lock()
        else:
            lock_token = self._lock()

        # Lock and release lock
        if args["stop"]:

            payload = {"message": "PTZ move stop, lock released", "status": 200}
            self._unlock()

        else:

            payload = {"message": "PTZ move applied", "status": 200, "lock_token": lock_token}

        # Apply PTZ move
        rcp_service = request.app["rcp_services"][self.cam_id]
        yield from rcp_service.move_ptz(**args)

        return aiohttp.web.json_response(payload, status=200)
