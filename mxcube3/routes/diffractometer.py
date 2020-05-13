from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json

from flask import Response, jsonify, request
from flask_restx import Namespace, Resource, fields

from . import signals
from mxcube3 import blcontrol
from mxcube3.core import beamlineutils, utils
from mxcube3.core import loginutils
from mxcube3.core import models

ns = Namespace(
    "diffractometer",
    description="Diffractometer operations",
    path="/mxcube/api/v0.1/diffractometer",
    decorators=[loginutils.valid_login_only]
)


@ns.route("/phase")
@ns.response(409, "On error")
class PhaseResource(Resource):
    @ns.produces("application/json")
    @ns.marshal_with(ns.model("DiffractometerCurrentPhaseModel",{
        "current_phase": fields.String(readonly=True, description="Phase")
    }))
    def get(self):
        """
        Retrieve the current phase in the diffractometer.
        """
        data = {"current_phase": blcontrol.beamline.diffractometer.get_current_phase()}
        return data, 200

    @ns.produces("application/json")
    @ns.response(200, "")
    @ns.expect(ns.model("DiffractometerPhaseModel",{
        "phase": fields.String(readonly=True, description="Phase, one of")
    }))
    @loginutils.require_control
    def put(self):
        """
        Set the diffractometer phase
        """
        params = ns.payload
        phase = params["phase"]
        beamlineutils.diffractometer_set_phase(phase)
        return Response(status=200)


@ns.route("/phaselist")
@ns.response(409, "On error")
class PhaseListResource(Resource):
    @ns.produces("application/json")
    @ns.marshal_with(ns.model("DiffractometerPhaseListModel",{
        "phase_list": fields.List(fields.String, readonly=True, description="Avialable phases")
    }))
    def get(self):
        """
        Retrieve a list of the available phases
        """
        return  {"phase_list": blcontrol.beamline.diffractometer.get_phase_list()}, 200



@ns.route("/platemode")
@ns.response(409, "On error")
class PlateModeResource(Resource):
    @ns.produces("application/json")
    @ns.marshal_with(ns.model("DiffractometerPlateModeModel",{
        "md_in_plate_mode": fields.Boolean(readonly=True, description="Phase")
    }))
    def get(self):
        """
        Returns: 
            (bool): Diffractometer plate mode
        """
        md_in_plate_mode = blcontrol.beamline.diffractometer.in_plate_mode()
        return {"md_in_plate_mode": md_in_plate_mode}, 200


@ns.route("/movables/state")
@ns.response(409, "On error")
class MovablesStateResource(Resource):
    @ns.produces("application/json")
    def get(self):
        ret = utils.get_centring_motors_info()
        ret.update(utils.get_light_state_and_intensity())
        resp = jsonify(ret)
        resp.status_code = 200
        return resp

@ns.route("/aperture")
@ns.response(409, "On error")
class ApertureResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "")
    @ns.marshal_with(ns.model('CurrentApertureModel', {
        'apertureList': fields.List(fields.Float, readonly=True, description="List of avialable apertures in microns"),
        'currentAperture': fields.Float(readonly=True, description="Current apperture in microns"),
    }))
    def get(self):
        """
        Get aperture
        """
        ret = {}
        aperture_list, current_aperture = beamlineutils.get_aperture()
        ret.update({"apertureList": aperture_list, "currentAperture": current_aperture})
        
        return ret, 200


    @ns.produces("application/json")
    @ns.response(200, "")
    @ns.expect(ns.model("ApertureDiameterModel",{
        "diameter": fields.Float(readonly=True, description="Phase, one of")
    }))
    def put(self):
        """
        Set aperture
        """
        params = ns.payload
        new_pos = params["diameter"]
        beamlineutils.set_aperture(new_pos)

        return Response(status=200)


@ns.route("/info")
@ns.response(409, "On error")
class DiffractometerInfoResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "")
    def get(self):
        resp = jsonify(beamlineutils.diffractometer_get_info())
        resp.status_code = 200
        return resp

