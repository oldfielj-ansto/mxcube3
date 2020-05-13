from flask_restx import Model, fields


def register_model(ns, model):
    return ns.add_model(model.name, model)


SampleViewDataModel = Model('SampleViewDataModel', {
    'pixelsPerMm': fields.List(fields.Float, readonly=True, description="Pixels per milimeter x and y"), 
    'imageWidth': fields.Float(readonly=True, description="Image width"),
    'imageHeight': fields.Float(readonly=True, description="Image height"),
    'format': fields.String(readonly=True, description="Video format"),
    'sourceIsScalable': fields.Boolean(readonly=True, description="Does video suport scaling"),
    'scale': fields.Float(readonly=True, description="Current scale"), 
    'videoSizes': fields.List(fields.Float, readonly=True, description="List of suported video sizes"), 
    'videoHash': fields.String(readonly=True, description="Video hash"), 
    'position': fields.List(fields.Float, readonly=True, description="Position of beam"), 
    'shape': fields.String(readonly=True, description="Beam shape"),
    'size_x': fields.Float(readonly=True, description="Beam width in mm"), 
    'size_y': fields.Float(readonly=True, description="Beam height in mm"), 
    'apertureList': fields.List(fields.Float, readonly=True, description="List of avialable apertures in microns"),
    'currentAperture': fields.Float(readonly=True, description="Current apperture in microns"),
})


WidthHeightModel = Model('WidthHeightModel',{
    "width": fields.Float(readonly=True, description="Image width"),
    "height": fields.Float(readonly=True, description="Image height"),
})


ZoomLevelModel = Model("ZoomLevelModel", {
    "level": fields.Float(readonly=True, description="Zoom level"),
})


PixelsPermmModel = Model("PixelsPermmModel", {
    'pixelsPerMm': fields.List(fields.Float, readonly=True, description="Pixels per milimeter x and y"),
})


ClicksLeftModel = Model("ClicksLeftModel", {
    "clicksLeft": fields.Integer(readonly=True, description="Clicks left"),
})


ScreenPositionModel = Model("ScreenPositionModel", {
    "x": fields.Float(readonly=True, description="x position in pixels"),
    "y": fields.Float(readonly=True, description="y postiion in pixels"),
})


ClickPositionModel = Model("ClickPositionModel",{
    "clickPos": fields.Nested(ScreenPositionModel)
})


CentringMethodModel = Model("CentringMethodModel", {
    "centringMethod": fields.String(readonly=True, description="Centring method"),
})

WorkflowModel = Model("WorkflowModel", {
    "wfname": fields.String(readonly=True, description="Workflow name"),
    "wfpath": fields.String(readonly=True, description="Workflow path"),
    "requires": fields.List(fields.String)
})

WorkflowListModel = Model("WorkflowListModel", {
    "*": fields.Wildcard(fields.Nested(WorkflowModel), description="Workflow name")
})

WorkflowsModel = Model("WorkflowsModel", {
    "workflows": fields.Nested(WorkflowListModel)
})

SampleChangerCapacityPairModel = Model("SampleChangerCapacityPairModel", {
    "num_baskets": fields.Integer(readonly=True, description="Number of baskets in sample changer"),
    "num_samples": fields.Integer(readonly=True, description="Number of samples per basket"),
})

SampleChangerCapacityModel = Model("SampleChangerCapacityModel",{
    "capacity": fields.Nested(SampleChangerCapacityPairModel),
})

SampleChangerSampleLocationModel = Model("SampleChangerSampleLocationModel",{
    "location": fields.String(readonly=True, description="Sample location"),
    "sampleID": fields.String(readonly=True, description="Sample ID"),
})

SampleChangerStateModel = Model("SampleChangerStateModel",{
    "state": fields.String(readonly=True, description="Sample changer state (READY, BUSY, UNKNOWN)")
})

SampleChangerLoadedSampleModel = Model("SampleChangerLoadedSampleModel",{
    "address": fields.String(readonly=True, description="Loaded sample address, sperated with :"),
    "barcode": fields.String(readonly=True, description="Loaded sample barcode"),
})

UserModel = Model("User", {
    "loginID": fields.String(readonly=True, description="User name"),
    "host": fields.String(readonly=True, description="hostname"),
    "sid": fields.String(readonly=True, description="Session ID"),
    "operator": fields.Boolean(readonly=True, description="Is user operator"),
    "name": fields.String(readonly=True, description="Full name"),
    "requestsControl": fields.Boolean(readonly=True, description="Is the user requsting control"),
    "message": fields.String(readonly=True, description="Chat message"),
    "socketio_sid": fields.String(readonly=True, description="Session ID"),
    "limsData": fields.Raw(readonly=True, description="User LIMS data")
})

FileSuffixModel = Model("FileSuffixModel",{
    "fileSuffix": fields.String(readonly=True, description="File suffix"),
})
