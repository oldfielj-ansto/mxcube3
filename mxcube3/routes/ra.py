# -*- coding: utf-8 -*-
import gevent
import logging
from flask import (
    session,
    jsonify,
    Response,
    request,
    make_response,
    copy_current_request_context,
)

from flask_restx import Namespace, Resource, fields

from mxcube3 import socketio
from mxcube3 import mxcube

from mxcube3 import blcontrol
from mxcube3.core import loginutils
from mxcube3.core import models

ns = Namespace(
    "remoteaccess",
    description="Sample view operations",
    path="/mxcube/api/v0.1/ra/",
    decorators=[loginutils.valid_login_only]
)

user_model = models.register_model(ns, models.UserModel)

@ns.route("/request_control")
class RequestControlResource(Resource):
    @ns.expect(user_model)
    @ns.response(200, "")
    @ns.produces("application/json")
    def post(self):
        """
        Request control
        """

        @copy_current_request_context
        def handle_timeout_gives_control(sid, timeout=30):
            gevent.sleep(timeout)

            if mxcube.TIMEOUT_GIVES_CONTROL:
                user = loginutils.get_user_by_sid(sid)

                # Pass control to user if still waiting
                if user.get("requestsControl"):
                    toggle_operator(sid, "Timeout expired, you have control")

        data = ns.payload
        remote_addr = loginutils.remote_addr()

        # Is someone already asking for control
        for observer in loginutils.get_observers():
            if observer["requestsControl"] and observer["host"] != remote_addr:
                msg = "Another user is already asking for control"
                return make_response(msg, 409)

        user = loginutils.get_user_by_sid(session.sid)

        user["name"] = data["name"]
        user["requestsControl"] = data["control"]
        user["message"] = data["message"]

        observers = loginutils.get_observers()
        gevent.spawn(handle_timeout_gives_control, session.sid, timeout=10)

        socketio.emit("observersChanged", observers, namespace="/hwr")

        return make_response("", 200)


@ns.route("/take_control")
class TakeControlResource(Resource):
    @ns.response(200, "")
    @ns.produces("application/json")
    def post(self):
        """
        Take control
        """
        # Already master do nothing
        if loginutils.is_operator(session.sid):
            return make_response("", 200)

        # Not inhouse user so not allowed to take control by force,
        # return error code
        if not session["loginInfo"]["loginRes"]["Session"]["is_inhouse"]:
            return make_response("", 409)

        toggle_operator(session.sid, "You were given control")

        return make_response("", 200)


@ns.route("/give_control")
class GiveControlResource(Resource):
    @ns.expect(ns.model("SessionIDModel", {
        "sid": fields.String(readonly=True, description="Session ID"),
    }))
    @ns.response(200, "")
    @ns.produces("application/json")
    def post(self):
        """
        Give control
        """
        sid = ns.payload.get("sid")
        toggle_operator(sid, "You were given control")

        return make_response("", 200)


def toggle_operator(new_op_sid, message):
    current_op = loginutils.get_operator()

    new_op = loginutils.get_user_by_sid(new_op_sid)
    loginutils.set_operator(new_op["sid"])
    new_op["message"] = message

    observers = loginutils.get_observers()

    # Append the new data path so that it can be updated on the client
    new_op["rootPath"] = blcontrol.beamline.session.get_base_image_directory()

    # Current op might have logged out, while this is happening
    if current_op:
        current_op["rootPath"] = blcontrol.beamline.session.get_base_image_directory()
        current_op["message"] = message
        socketio.emit(
            "setObserver", current_op, room=current_op["socketio_sid"], namespace="/hwr"
        )

    socketio.emit("observersChanged", observers, namespace="/hwr")
    socketio.emit("setMaster", new_op, room=new_op["socketio_sid"], namespace="/hwr")


def remain_observer(observer_sid, message):
    observer = loginutils.get_user_by_sid(observer_sid)
    observer["message"] = message

    socketio.emit(
        "setObserver", observer, room=observer["socketio_sid"], namespace="/hwr"
    )


@ns.route("/")
class ObserversResource(Resource):
    @ns.response(200, "")
    @ns.produces("application/json")
    def get(self):
        """
        List all observers
        """
        data = {
            "observers": loginutils.get_observers(),
            "sid": session.sid,
            "master": loginutils.is_operator(session.sid),
            "observerName": loginutils.get_observer_name(),
            "allowRemote": mxcube.ALLOW_REMOTE,
            "timeoutGivesControl": mxcube.TIMEOUT_GIVES_CONTROL,
        }

        return jsonify(data=data)


@ns.route("/allow_remote")
class AllowRemoteResource(Resource):
    @ns.expect(ns.model("AllowRemoteModel", {
        "allow": fields.Boolean(readonly=True, description="Allow remote"),
    }))
    @ns.response(200, "")
    @ns.produces("application/json")
    def post(self):
        """
        Enable remote
        """
        allow = ns.payload.get("allow")

        if mxcube.ALLOW_REMOTE and allow == False:
            socketio.emit("forceSignoutObservers", {}, namespace="/hwr")

        mxcube.ALLOW_REMOTE = allow

        return Response(status=200)


@ns.route("/timeout_gives_control")
class TimeoutControlResource(Resource):
    @ns.expect(ns.model("TimeoutGivesControlModel", {
        "timeoutGivesControl": fields.Boolean(readonly=True, description="Timeout gives control"),
    }))
    @ns.response(200, "")
    @ns.produces("application/json")
    def post(self):
        """
        Enable timeout gives control
        """
        control = ns.payload.get("timeoutGivesControl")
        mxcube.TIMEOUT_GIVES_CONTROL = control

        return Response(status=200)


def observer_requesting_control():
    observer = None

    for o in loginutils.get_observers():
        if o["requestsControl"]:
            observer = o

    return observer

@ns.route("/request_control_response")
class TimeoutControlResource(Resource):
    @ns.expect(ns.model("GiveControlModel", {
        "giveControl": fields.Boolean(readonly=True, description="Pass control"),
        "message": fields.String(readonly=True, description="Reply message"),
    }))
    @ns.response(200, "")
    @ns.produces("application/json")
    def post(self):
        """
        Reply to a "reuqest for control" request
        """
        data = ns.payload
        new_op = observer_requesting_control()

        # Request was denied
        if not data["giveControl"]:
            remain_observer(new_op["sid"], data["message"])
        else:
            toggle_operator(new_op["sid"], data["message"])

        new_op["requestsControl"] = False

        return make_response("", 200)


@ns.route("/chat")
class TimeoutControlResource(Resource):
    @ns.expect(ns.model("GiveControlModel", {
        "sid": fields.String(readonly=True, description="Session ID"),
        "message": fields.String(readonly=True, description="Chat message"),
    }))
    @ns.response(200, "")
    @ns.produces("application/json")
    def post(self):
        """
        Post a chat message
        """
        message =ns.payload.get("message", "")
        sid = ns.payload.get("sid", "")

        if message and sid:
            loginutils.append_message(message, sid)

        return Response(status=200)

    @ns.response(200, "")
    @ns.produces("application/json")
    def get(self):
        """
        Returns a list of all chat messages
        """
        return jsonify({"messages": loginutils.get_all_messages()})


@socketio.on("connect", namespace="/hwr")
@loginutils.ws_valid_login_only
def connect():
    user = loginutils.get_user_by_sid(session.sid)

    # Make sure user is logged, session may have been closed i.e by timeout
    if user:
        user["socketio_sid"] = request.sid

    # (Note: User is logged in if operator)
    if loginutils.is_operator(session.sid):
        loginutils.emit_pending_events()

        if (
            not blcontrol.beamline.queue_manager.is_executing()
            and not loginutils.DISCONNECT_HANDLED
        ):
            loginutils.DISCONNECT_HANDLED = True
            socketio.emit("resumeQueueDialog", namespace="/hwr")
            msg = "Client reconnected, Queue was previously stopped, asking "
            msg += "client for action"
            logging.getLogger("HWR").info(msg)


@socketio.on("disconnect", namespace="/hwr")
@loginutils.ws_valid_login_only
def disconnect():
    if (
        loginutils.is_operator(session.sid)
        and blcontrol.beamline.queue_manager.is_executing()
    ):

        loginutils.DISCONNECT_HANDLED = False
        blcontrol.beamline.queue_manager.pause(True)
        logging.getLogger("HWR").info("Client disconnected, pausing queue")


@socketio.on("setRaMaster", namespace="/hwr")
@loginutils.ws_valid_login_only
def set_master(data):
    loginutils.emit_pending_events()

    return session.sid


@socketio.on("setRaObserver", namespace="/hwr")
@loginutils.ws_valid_login_only
def set_observer(data):
    name = data.get("name", "")
    observers = loginutils.get_observers()
    observer = loginutils.get_user_by_sid(session.sid)

    if observer and name:
        observer["name"] = name
        socketio.emit("observerLogin", observer, include_self=False, namespace="/hwr")

    socketio.emit("observersChanged", observers, namespace="/hwr")

    return session.sid
