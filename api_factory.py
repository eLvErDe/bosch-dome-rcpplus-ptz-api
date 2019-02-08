"""
Define the REST API for JWT authentication
"""


# pylint: disable=line-too-long


import asyncio
import logging
import functools
import os
import inspect
import aiohttp.web
import aiohttp_swagger
import aiohttp_cors
import aiohttp_jinja2
import jinja2
import api_middlewares
import resources
import services


class ApiFactory(object):
    """
    Define the REST API for JWT authentication
    """

    def __init__(self, loop=None, config=None):
        """ Create the aiohttp application """

        self.logger = logging.getLogger(self.__class__.__name__)
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        self.config = config

        swagger_url = self.prefix_context_path("/doc")

        self.app = aiohttp.web.Application(loop=loop, middlewares=[functools.partial(api_middlewares.rest_error_middleware, logger=self.logger)])
        self.app.factory = self

        self.app.router.add_route("GET", "/", lambda x: aiohttp.web.HTTPFound(swagger_url))
        if self.config.context_path != "/":
            self.app.router.add_route("GET", self.config.context_path, lambda x: aiohttp.web.HTTPFound(swagger_url))
        self.app.router.add_route("GET", self.config.context_path + "/", lambda x: aiohttp.web.HTTPFound(swagger_url))
        for cam in self.config.cams.keys():
            self.app.router.add_route("GET", self.prefix_context_path("/cams/%s/ptz/move" % cam), resources.PtzMove(cam).get)
        self.app.router.add_route("GET", self.prefix_context_path("/interfaces/ptz/move"), resources.InterfacePtzMove().get)
        self.app.router.add_static(self.prefix_context_path("/static"), os.path.join(self.config.PROJECT_ROOT, "static"))

        # Setup Swagger
        # bundle_params is a GitHub patch not released
        # in any aiohttp_swagger package
        setup_swagger_sign = inspect.signature(aiohttp_swagger.setup_swagger)
        kwargs = {}
        if "bundle_params" in setup_swagger_sign.parameters:
            kwargs["bundle_params"] = {"layout": "BaseLayout"}

        aiohttp_swagger.setup_swagger(
            app=self.app,
            description="API to move PTZ on Bosch camera using RCP+ protocol",
            title="PTZ API for Bosch RCP+",
            api_version="1.0",
            contact="acecile@le-vert.net",
            swagger_url=swagger_url,
            **kwargs
        )

        # Setup CORS
        if self.config.allow_origin:
            self.cors = aiohttp_cors.setup(
                self.app,
                defaults={self.config.allow_origin: aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")},
            )
            for route in self.app.router.routes():
                if not isinstance(route.resource, aiohttp.web_urldispatcher.StaticResource):
                    self.cors.add(route)

        # Setup Jinja2 templates
        self.jinja2env = aiohttp_jinja2.setup(self.app, loader=jinja2.FileSystemLoader(os.path.join(self.config.PROJECT_ROOT, "templates")))
        self.jinja2env.globals["config"] = self.config
        self.jinja2env.globals["static_path"] = self.prefix_context_path("/static")

        # Print configured routes
        self.print_routes()

        # Setup services
        self.app.on_startup.append(self.setup_rcp_services)
        self.app.on_shutdown.append(self.close_rcp_services)

    def url_for(self, name):
        """ Get relative URL for a given route named """
        return self.app.router.named_resources()[name].url()

    @staticmethod
    def route_join(*args):
        """ Simple helper to compute relative URLs """
        route_url = "/".join([x.strip("/") for x in args])
        if not route_url.startswith("/"):
            route_url = "/" + route_url
        return route_url

    def prefix_context_path(self, *args):
        """ Construct a relative URL with context path """
        return self.route_join(self.config.context_path, *args)

    def print_routes(self):
        """ Log all configured routes """

        for route in self.app.router.routes():
            route_info = route.get_info()
            if "formatter" in route_info:
                url = route_info["formatter"]
            elif "path" in route_info:
                url = route_info["path"]
            elif "prefix" in route_info:
                url = route_info["prefix"]
            else:
                url = "Unknown type of route %s" % route_info

            self.logger.info("Route has been setup %s at %s", route.method, url)

    @staticmethod
    @asyncio.coroutine
    def setup_rcp_services(app):
        """ Instance PTZ service for each camera """

        app["aiohttp_session"] = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10))
        app["rcp_services"] = {}

        for cam, cam_params in app.factory.config.cams.items():
            app["rcp_services"][cam] = services.AsyncRcpClient(
                url=cam_params["url"], username=cam_params["username"], password=cam_params["password"], name=cam, session=app["aiohttp_session"]
            )

    @staticmethod
    @asyncio.coroutine
    def close_rcp_services(app):
        """ Shutdown aiohttp session used by PTZ services """

        yield from app["aiohttp_session"].close()
