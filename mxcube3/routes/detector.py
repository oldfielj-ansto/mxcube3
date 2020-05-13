from flask import jsonify

from mxcube3.core import beamlineutils
from mxcube3.core import loginutils
from mxcube3.core import models

from flask_restx import Namespace, Resource

ns = Namespace(
    "detector",
    description="Detetor operations",
    path="/mxcube/api/v0.1/detector",
    decorators=[loginutils.valid_login_only]
)

file_suffix_model = models.register_model(ns, models.FileSuffixModel)

@ns.route("/")
@ns.response(409, "on error")
class CameraResource(Resource):
    @ns.marshal_with(file_suffix_model)
    @ns.produces("application/json")
    def get(self):
        """
        Retrieves general info from the detector.
            example:
                {"filetype": "h5"},
        """
        return {"fileSuffix": beamlineutils.get_detector_info()}, 200