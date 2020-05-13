from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from . import signals

from flask import Response, jsonify, request
from flask_restx import Namespace, Resource, fields

from mxcube3 import blcontrol
from mxcube3.core import limsutils
from mxcube3.core import scutils
from mxcube3.core import loginutils
from mxcube3.core import models

from mxcube3.core.qutils import UNCOLLECTED, SAMPLE_MOUNTED, COLLECTED
from mxcube3.core.scutils import set_current_sample

ns = Namespace(
    "samplechanger",
    description="Sample changer related operations",
    path="/mxcube/api/v0.1/sample_changer",
    decorators=[loginutils.valid_login_only]
)


sample_changer_state_model = models.register_model(ns, models.SampleChangerStateModel)
sample_changer_loaded_sample_model = models.register_model(ns, models.SampleChangerLoadedSampleModel)
sample_changer_capacity_model = models.register_model(ns, models.SampleChangerCapacityModel)
sample_changer_sample_location_model = models.register_model(ns, models.SampleChangerSampleLocationModel)


@ns.route("/samples_list")
class SampleListResource(Resource):
    @ns.response(200, "Sample list")
    @ns.produces("application/json")
    def get(self):
        """
        Returns the current sample list
        """
        return jsonify(limsutils.sample_list_get())


@ns.route("/state")
class StateResource(Resource):
    @ns.produces("application/json")
    @ns.marshal_with(sample_changer_state_model)
    def get(self):
        """
        Returns the sample changer state
        """
        state = blcontrol.beamline.sample_changer.get_status().upper()
        return {"state": state}, 200


@ns.route("/loaded_sample")
class LoadedSampleResource(Resource):
    @ns.produces("application/json")
    @ns.marshal_with(sample_changer_loaded_sample_model)
    def get(self):
        """
        Get currently loaded sample
        """
        address, barcode = scutils.get_loaded_sample()
        return {"address": address, "barcode": barcode}, 200


@ns.route("/contents")
class ContentseResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object, sample changer contents")
    def get(self):
        """
        Get sample changer content
        """
        return jsonify(scutils.get_sc_contents())


@ns.route("/select/<loc>")
@ns.param('loc', 'Sample changer location, : seperated string')
class SelectSampleResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object, sample changer contents")
    @loginutils.require_control
    def get(self, loc):
        """
        Select sample at location <loc>
        """
        blcontrol.beamline.sample_changer.select(loc)
        return scutils.get_sc_contents()


@ns.route("/scan/<loc>")
@ns.param('loc', 'Sample changer location, : seperated string')
class ScanResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object, sample changer contents")
    @loginutils.require_control
    def get(self, loc):
        """
        Recursively scan the sample changer for contents starting from <loc>
        """
        blcontrol.beamline.sample_changer.scan(loc, True)
        return scutils.get_sc_contents()


@ns.route("/unmount_current")
@ns.response(409, "Could not unmount sample")
class UnMountCurrentSampleResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object, sample changer contents")
    @loginutils.require_control
    def post(self):
        """
        Unmount currenly loaded sample
        """
        try:
            res = scutils.unmount_current()
        except Exception as ex:
            res = (
                "Cannot unload sample",
                409,
                {"Content-Type": "application/json", "message": str(ex)},
            )
        
        return jsonify(res)


@ns.route("/mount")
@ns.response(409, "Could not mount sample")
class MountSampleResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object, sample changer contents")
    @ns.expect(sample_changer_sample_location_model)
    @loginutils.require_control
    def post(self):
        """
        Mount currenly loaded sample
        """
        resp = Response(status=200)

        try:
            resp = jsonify(scutils.mount_sample(ns.payload))
        except Exception as ex:
            resp = (
                "Cannot load sample",
                409,
                {"Content-Type": "application/json", "message": str(ex)},
            )

        return resp


@ns.route("/unmount")
@ns.response(409, "Could not unmount sample")
class UnMountSampleResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object, sample changer contents")
    @ns.expect(sample_changer_sample_location_model)
    @loginutils.require_control
    def post(self):
        """
        Un-mount currenly loaded sample
        """
        try:
            resp = jsonify(scutils.unmount_sample(ns.payload))
        except Exception as ex:
            return (
                "Cannot unload sample",
                409,
                {"Content-Type": "application/json", "message": str(ex)},
            )
        return resp


@ns.route("/capacity")
@ns.response(409, "Could not get sample changer capacity")
class CapacitySampleResource(Resource):
    @ns.produces("application/json")
    @loginutils.require_control
    def get(self):
        """
        Returns the sample changer capacity
        """
        try:
            ret = scutils.get_capacity()
        except Exception:
            ns.abort(409)
        else:
            return {"capacity": ret}, 200


@ns.route("/get_global_state")
@ns.response(409, "Could not get sample changer maintenance state")
class MaintenanceStateResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object")
    def get(self):
        """
        Returns the state of the SampleChangerMaintenance hardware object
        """
        try:
            ret = scutils.get_global_state()

            if ret:
                state, cmdstate, msg = ret
            else:
                return jsonify(ret)

        except Exception:
            return Response(status=409)
        else:
            return jsonify(state=state, commands_state=cmdstate, message=msg)


@ns.route("/get_initial_state")
@ns.response(409, "Could not get initial state")
class InitialStateResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object")
    def get(self):
        """
        Returns the "initial" state of the sample changer:
            {
                "state": str,
                "loaded_sample": str,
                "contents": { ....}
                "global_state": {"global_state": str, "commands_state": str},
                "cmds": {"cmds": ...},
                "msg": str
                "plate_mode": bool
            }
        """
        return jsonify(scutils.get_initial_state())

@ns.route("/get_maintenance_cmds")
@ns.response(409, "Could not get maintenance commands")
class MaintenanceCommandsResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object")
    def get(self):
        """
        Returns an object conatiaing the avialable maintenace commands
        """
        try:
            ret = scutils.get_maintenance_cmds()
        except Exception:
            return Response(status=409)
        else:
            return jsonify(cmds=ret)


@ns.route("/send_command/<cmdparts>")
@ns.response(406, "Could execute command")
class MaintenanceCommandsResource(Resource):
    @ns.produces("application/json")
    @ns.response(200, "JSON Object")
    @loginutils.require_control
    def get(self, cmdparts):
        """
        Execute the command passed in <cmdparts>
        """
        try:
            ret = blcontrol.beamline.sample_changer_maintenance.send_command(cmdparts)
        except Exception as ex:
            msg = str(ex)
            msg = msg.replace("\n", " - ")
            return (
                "Cannot execute command",
                406,
                {"Content-Type": "application/json", "message": msg},
            )
        else:
            return jsonify(response=ret)