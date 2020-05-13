import logging

from flask import session, request, jsonify, make_response, redirect
from flask_restx import Namespace, Resource, fields

from mxcube3.core import loginutils
from mxcube3.core import models


def deny_access(msg):
    resp = jsonify({"msg": msg})
    resp.code = 409
    return resp

ns = Namespace(
    "login",
    description="Login related operations",
    path="/mxcube/api/v0.1",
)

@ns.route("/login")
@ns.response(409, "On error")
class LoginResource(Resource):
    @ns.produces("application/json")
    @ns.expect(ns.model("UserLoginModel",{
         "proposal": fields.String(readonly=True, description="proposal"),
         "password": fields.String(readonly=True, description="password")
    }))
    def post(self):
        """
        Login to mxcube application.

        Returns: 
            (object):

            {
                'status':{ 'code': 'ok', 'msg': msg },
                'Proposal': proposal,
                'session': todays_session,
                'local_contact': local_contact,
                'person': someone,
                'laboratory': a_laboratory
            }
        """
        login_id = ns.payload.get("proposal", "")
        password = ns.payload.get("password", "")

        try:
            res = jsonify(loginutils.login(login_id, password))
        except Exception as ex:
            msg = "[LOGIN] User %s could not login (%s)" % (login_id, str(ex))
            logging.getLogger("MX3.HWR").info(msg)
            res = deny_access(str(ex))

        return res


@ns.route("/signout")
@ns.response(409, "On error")
class SingoutResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "")
    def get(self):
        """
        Signout from Mxcube3 and reset the session
        """
        loginutils.signout()

        return make_response("", 200)


@ns.route("/login_info")
@ns.response(409, "On error")
class LoginInfoResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "")
    def get(self):
        """
        Retrieve session/login info

        Returns: 
            (object):
            {
                'synchrotron_name': synchrotron_name,
                'beamline_name': beamline_name,
                'loginType': loginType,
                'loginRes': {'status':{ 'code': 'ok', 'msg': msg },
                'Proposal': proposal, 'session': todays_session,
                'local_contact': local_contact,
                'person': someone,
                'laboratory': a_laboratory'
            }
        """
        login_info = session.get("loginInfo")

        user, res = loginutils.login_info(login_info)

        # Redirect the user to login page if for some reason logged out
        # i.e. server restart
        if not user:
            response = redirect("/login", code=302)
        else:
            response = jsonify(res)

        return response


@ns.route("/send_feedback")
@ns.response(409, "On error")
class SendFeedbackResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "")
    def post(self):
        loginutils.send_feedback()
        return make_response("", 200)
