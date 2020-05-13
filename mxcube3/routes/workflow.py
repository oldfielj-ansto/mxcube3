# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from flask import Response, jsonify, request
from flask_restx import Namespace, Resource, fields

from mxcube3 import socketio

from mxcube3.core import wfutils
from mxcube3.core import loginutils
from mxcube3.core import models


ns = Namespace(
    "workflow",
    description="Workflow related operations",
    path="/mxcube/api/v0.1/workflow",
    decorators=[loginutils.valid_login_only]
)


workflow_model = ns.model("WorkflowModel", {
    "wfname": fields.String(readonly=True, description="Workflow name"),
    "wfpath": fields.String(readonly=True, description="Workflow path"),
    "requires": fields.List(fields.String)
})


workflow_list_model = ns.model("WorkflowListModel", {
    "*": fields.Wildcard(fields.Nested(workflow_model), description="Workflow name")
})

workflows_model = models.register_model(ns, models.WorkflowsModel)


@ns.route("/")
class WorklfowResource(Resource):
    @ns.produces("application/json")
    @ns.marshal_with(workflows_model)
    def get(self):
        """
        Returns a JSON object with the avaialble workflows
        """
        return wfutils.get_available_workflows(), 200

    @ns.response(200, "")
    @ns.produces("application/json")
    def post(self):
        """
        "Pass parameters submitted by user to workflow"
        """
        data = request.get_json()
        wfutils.submit_parameters(data)
        return Response(status=200)


@ns.route("/dialog/<wf>")
@ns.param('wf', 'The workflow id')
class WorklfowDialogResource(Resource):
    @ns.response(200, "")
    @ns.produces("application/json")
    def get(self, wf):
        """
        Show dialog with form, specified by a JSONSchema, for paramter input,
        for wokflow with id <wf>
        """
        dialog = wfutils.test_workflow_dialog(wf)
        socketio.emit("workflowParametersDialog", dialog, namespace="/hwr")

        return Response(status=200)