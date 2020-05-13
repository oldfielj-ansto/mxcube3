from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json

from flask import Response, jsonify, request, make_response
from flask_restx import Namespace, Resource, fields

from mxcube3 import blcontrol
from mxcube3.core import beamlineutils
from mxcube3.core import loginutils
from mxcube3.core import models

ns = Namespace(
    "beamline",
    description="Beamline operations",
    path="/mxcube/api/v0.1/beamline",
    decorators=[loginutils.valid_login_only]
)

@ns.route("/")
class BeamlineResource(Resource):
    @ns.response(200, "Beamline attributes")
    @ns.produces("application/json")
    def get(self):
        """
        Returns all beamline attribues
        """
        return jsonify(beamlineutils.beamline_get_all_attributes())


@ns.route("/<name>/abort")
@ns.response(520, "Could not abort action")
@ns.param("name", "name of action to abort")
class AbortBeamlineActionResource(Resource):
    @ns.response(200, "")
    @ns.produces("application/json")
    @loginutils.require_control
    def get(self, name):
        """
        Aborts an action in progress.

        Args: 
            name (str): Owner / Actuator of the process/action to abort
        """
        try:
            beamlineutils.beamline_abort_action(name)
        except Exception:
            err = str(sys.exc_info()[1])
            return make_response(err, 520)
        else:
            logging.getLogger("user_level_log").error("Aborting set on %s." % name)
            return make_response("", 200)


@ns.route("/<name>/run")
@ns.response(520, "Could not run action")
@ns.param("name", "name of action to abort")
class RunBeamlineActionResource(Resource):
    @ns.expect(ns.model("ActionParameters", {
        "parameters": fields.Raw(readonly=True, description="Parameters"),
    }))
    @ns.response(200, "")
    @ns.produces("application/json")
    @loginutils.require_control
    def post(self, name):
        """
        Starts a beamline action; POST payload is a json-encoded object with
        'parameters' as a list of parameters

        Args: 
            name (str): action to run
        """
        try:
            params = ns.payload["parameters"]
        except Exception:
            params = []

        try:
            beamlineutils.beamline_run_action(name, params)
        except Exception as ex:
            return make_response(str(ex), 520)
        else:
            return make_response("{}", 200)


@ns.route("/<name>")
@ns.response(520, "Could not find/set attribute")
@ns.param("name", "Attribute name")
class BeamlineAttributeResource(Resource):
    @ns.expect(ns.model("AttributeValue", {
        "value": fields.Raw(readonly=True, description="value"),
    }))
    @ns.response(200, "")
    @ns.produces("application/json")
    @loginutils.require_control
    def put(self, name):
        """
        Tries to set < name > to value, replies with the following json:

            {name: < name > , value: < value > , msg: < msg > , state: < state >

        Where msg is an arbitrary msg to user, state is the internal state
        of the set operation(for the moment, VALID, ABORTED, ERROR).
        """
        param = ns.payload
        res, data = beamlineutils.beamline_set_attribute(name, param)

        if res:
            code = 200
        else:
            code = 520

        response = jsonify(data)
        response.code = code
        return response

    @ns.response(200, "")
    @ns.produces("application/json")
    def get(self, name):
        """
        Retrieves value of attribute < name > , replies with the following json:

            {name: < name > , value: < value > , msg: < msg > , state: < state >

        Where msg is an arbitrary msg to user, state is the internal state
        of the get operation(for the moment, VALID, ABORTED, ERROR).

        Replies with status code 200 on success and 520 on exceptions.
        """
        res, data = beamlineutils.beamline_get_attribute(name)

        response = jsonify(data)
        response.code = res
        return response


@ns.route("/beam")
class BeamResource(Resource):
    @ns.produces("application/json")
    @ns.marshal_with(ns.model("BeamInfoModel", {
        'position': fields.List(fields.Float, readonly=True, description="Position of beam"), 
        'shape': fields.String(readonly=True, description="Beam shape"),
        'size_x': fields.Float(readonly=True, description="Beam width in mm"), 
        'size_y': fields.Float(readonly=True, description="Beam height in mm"), 
        'apertureList': fields.List(fields.Float, readonly=True, description="List of avialable apertures in microns"),
        'currentAperture': fields.Float(readonly=True, description="Current apperture in microns"),
    }))
    def get(self):
        """
        Returns:
         (dict): {"position": , "shape": , "size_x": , "size_y": "apertureList":, "currentAperture":}
        """
        return beamlineutils.get_beam_info(), 200


@ns.route("/datapath")
class DataPatheResource(Resource):
    @ns.produces("application/json")
    @ns.marshal_with(ns.model("DataPathModel", {
        'path': fields.String(readonly=True, description="Data path"),
    }))
    def get(self):
        """
        Retrieve data directory from the session hwobj,
        this is specific for each beamline.
        """
        data = blcontrol.beamline.session.get_base_image_directory()
        return {"path": data}, 200


@ns.route("/prepare_beamline")
class PrepareBeamlineResource(Resource):
    @ns.response(200, "")
    @ns.produces("application/json")
    @loginutils.require_control
    def put(self):
        """
        Prepare the beamline for a new sample.
        """
        try:
            beamlineutils.prepare_beamline_for_sample()
        except Exception:
            msg = "Cannot prepare the Beamline for a new sample"
            logging.getLogger("HWR").error(msg)
            return Response(status=200)
        return Response(status=200)

