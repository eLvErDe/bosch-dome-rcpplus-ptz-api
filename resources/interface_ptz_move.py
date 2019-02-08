""" HTML interface providing JS joystick """


# pylint: disable=line-too-long


import asyncio
import aiohttp_jinja2


class InterfacePtzMove(object):  # pylint: disable=too-few-public-methods
    """ HTML interface providing JS joystick """

    @staticmethod
    @asyncio.coroutine
    def get(request):
        """
        ---
        description: Interface with PTZ JS joystick <br/><br/><h2><a href="interfaces/ptz/move">Open HTML interface</a></h2>
        produces:
        - text/html
        tags:
        - interface
        responses:
            200:
                description: Interface with PTZ JS joystick <br/><br/><h2><a href="interfaces/ptz/move">Open HTML interface</a></h2>
        """

        return aiohttp_jinja2.render_template("ptz_move.html", request, context={})
