# -*- coding: utf-8 -*-
import os
import json
import cPickle as pickle
import redis
import itertools
import xml.etree.ElementTree as et

import Utils

import queue_model_objects_v1 as qmo
import queue_entry as qe
import queue_model_enumerables_v1 as qme

from flask import jsonify
from mock import Mock
from mxcube3 import app as mxcube
from mxcube3 import socketio
from . import scutils
from . import limsutils

# Important: same constants as in constants.js
QUEUE_PAUSED = 'QueuePaused'
QUEUE_RUNNING = 'QueueStarted'
QUEUE_STOPPED = 'QueueStopped'
QUEUE_FAILED = 'QueueFailed'

SAMPLE_MOUNTED = 0x8
COLLECTED = 0x4
WARNING = 0x10
FAILED = 0x2
RUNNING = 0x1
UNCOLLECTED = 0x0
READY = 0

ORIGIN_MX3 = "MX3"
QUEUE_CACHE = {}


def node_index(node):
    """
    Get the position (index) in the queue, sample and node id of node <node>.

    :returns: dictionary on the form:
              {'sample': sample, 'idx': index, 'queue_id': node_id}
    """
    sample, index = None, None

    # RootNode nothing to return
    if isinstance(node, qmo.RootNode):
        sample, idx = None, None
    # For samples simply return the sampleID
    elif isinstance(node, qmo.Sample):
        sample = node.loc_str
    # TaskGroup just return the sampleID
    elif node.get_parent():
        if isinstance(node, qmo.TaskGroup):
            sample_model = node.get_parent()
        else:
            sample_model = node.get_parent().get_parent()

        sample = sample_model.loc_str
        task_groups = sample_model.get_children()
        group_list = [group.get_children() for group in task_groups]

        tlist = []

        for group in task_groups:
            if group.interleave_num_images:
                tlist.append(group)
            else:
                tlist.extend(group.get_children())

        try:
            index = tlist.index(node)
        except Exception:
            pass

    return {'sample': sample, 'idx': index, 'queue_id': node._node_id}


def load_queue_from_dict(queue_dict):
    """
    Loads the queue in queue_dict in to the current mxcube queue (mxcube.queue)

    :param dict queue_dict: Queue dictionary, on the same format as returned by
                            queue_to_dict
    """
    if queue_dict:
        item_list = []

        for sid in queue_dict['sample_order']:
            item_list.append(queue_dict[sid])

        queue_add_item(item_list)


def queue_to_dict(node=None):
    """
    Returns the dictionary representation of the queue

    :param TaskNode node: list of Node objects to get representation for,
                          queue root used if nothing is passed.

    :returns: dictionary on the form:
              { sampleID_1:{ sampleID_1: sid_1,
                             queueID: qid_1,
                             location: location_n
                             tasks: [task1, ... taskn]},
                             .
                             .
                             .
                sampleID_N:{ sampleID_N: sid_N,
                             queueID: qid_N,
                             location: location_n,
                             tasks: [task1, ... taskn]}

             where the contents of task is a dictionary, the content depends on
             the TaskNode type (DataCollection, Chracterisation, Sample). The
             task dict can be directly used with the set_from_dict methods of
             the corresponding node.
    """
    if not node:
        node = mxcube.queue.get_model_root()

    return reduce(lambda x, y: x.update(y) or x, queue_to_dict_rec(node), {})


def queue_to_json(node=None):
    """
    Returns the json representation of the queue

    :param TaskNode node: list of Node objects to get representation for,
                          queue root used if nothing is passed.

    :returns: json str on the form:
              [ { sampleID_1: sid_1,
                  queueID: qid_1,
                  location: location_n
                  tasks: [task1, ... taskn]},
                .
                .
                .
                { sampleID_N: sid_N,
                  queueID: qid_N,
                  location: location_n,
                  tasks: [task1, ... taskn]} ]

             where the contents of task is a dictionary, the content depends on
             the TaskNode type (Datacollection, Chracterisation, Sample). The
             task dict can be directly used with the set_from_dict methods of
             the corresponding node.
    """
    if not node:
        node = mxcube.queue.get_model_root()

    res = reduce(lambda x, y: x.update(y) or x, queue_to_dict_rec(node), {})
    return json.dumps(res, sort_keys=True, indent=4)


def queue_to_json_response(node=None):
    """
    Returns the http json response object with the json representation of the
    queue as data.

    :param TaskNode node: list of Node objects to get representation for,
                          queue root used if nothing is passed.

    :returns: Flask Response object
    """
    if not node:
        node = mxcube.queue.get_model_root()

    res = reduce(lambda x, y: x.update(y) or x, queue_to_dict_rec(node), {})
    return jsonify(res)


def get_node_state(node_id):
    """
    Get the state of the given node.

    :param TaskNode node: Node to get state for

    :returns: tuple containing (enabled, state)
              where state: {0, 1, 2, 3} = {in_queue, running, success, failed}
              {'sample': sample, 'idx': index, 'queue_id': node_id}
    """
    try:
        node, entry = get_entry(node_id)
    except:
        return (1, 0)

    executed = node.is_executed()
    enabled = node.is_enabled()
    failed = entry._execution_failed

    curr_entry = mxcube.queue.queue_hwobj.get_current_entry()
    running = mxcube.queue.queue_hwobj.is_executing and \
              (curr_entry == entry or curr_entry == entry._parent_container)

    if failed:
        state = FAILED
    elif executed:
        state = COLLECTED
    elif running:
        state = RUNNING
    else:
        state = UNCOLLECTED

    return (enabled, state)


def get_queue_state():
    """
    Return the dictionary representation of the current queue and its state

    :returns: dictionary on the form:
              {
                loaded: ID of currently loaded sample,
                queue: same format as queue_to_dict() but without sample_order,
                queueStatus: one of [QUEUE_PAUSED, QUEUE_RUNNING, QUEUE_STOPPED]
              }
    """
    queue = queue_to_dict()
    queue.pop("sample_order") if queue else queue

    res = { "loaded": scutils.get_current_sample(),
            "centringMethod": mxcube.CENTRING_METHOD,
            "autoMountNext": get_auto_mount_sample(),
            "autoAddDiffPlan": mxcube.AUTO_ADD_DIFFPLAN,
            "queue": queue,
            "queueStatus": queue_exec_state() }

    return res


def _handle_dc(sample_id, node, include_lims_data=False):
    parameters = node.as_dict()
    parameters["shape"] = getattr(node, 'shape', '')
    parameters["helical"] = node.experiment_type == qme.EXPERIMENT_TYPE.HELICAL

    parameters.pop('sample')
    parameters.pop('acquisitions')
    parameters.pop('acq_parameters')
    parameters.pop('centred_position')

    queueID = node._node_id
    enabled, state = get_node_state(queueID)
    parameters['subdir'] = parameters['path'].\
        split(mxcube.session.get_base_image_directory())[1][1:]

    pt = node.acquisitions[0].path_template

    parameters['fileName'] = pt.get_image_file_name().\
        replace('%' + ('%sd' % str(pt.precision)), int(pt.precision) * '#')

    parameters['fullPath'] = os.path.join(parameters['path'],
                                          parameters['fileName'])

    limsres = ''

    # Only add data from lims if explicitly asked for, since
    # its a operation that can take some time.
    if include_lims_data and mxcube.rest_lims:
        limsres = mxcube.rest_lims.get_dc(node.id)      

    res = {"label": "Data Collection",
           "type": "DataCollection",
           "parameters": parameters,
           "sampleID": sample_id,
           "taskIndex": node_index(node)['idx'],
           "queueID": queueID,
           "checked": node.is_enabled(),
           "state": state,
           "limstResultData": limsres,
           }

    return res


def _handle_wf(sample_id, node):
    queueID = node._node_id
    enabled, state = get_node_state(queueID)
    parameters = node.parameters
    parameters.update(node.path_template.as_dict())
    res = {"label": parameters['label'],
           "type": "Workflow",
           "name": node._type,
           "parameters": parameters,
           "sampleID": sample_id,
           "taskIndex": node_index(node)['idx'],
           "queueID": queueID,
           "checked": node.is_enabled(),
           "state": state
           }

    return res


def _handle_xrf(sample_id, node):
    queueID = node._node_id
    enabled, state = get_node_state(queueID)
    parameters = {"countTime": node.count_time,
                  "shape": node.shape}
    parameters.update(node.path_template.as_dict())
    parameters['path'] = parameters['directory']

    parameters['subdir'] = parameters['path'].\
        split(mxcube.session.get_base_image_directory())[1][1:]

    pt = node.path_template

    parameters['fileName'] = pt.get_image_file_name().\
        replace('%' + ('%sd' % str(pt.precision)), int(pt.precision) * '#')

    parameters['fullPath'] = os.path.join(parameters['path'],
                                          parameters['fileName'])
    model, entry = get_entry(queueID)

    res = {"label": "XRF Scan",
           "type": "XRFScan",
           "parameters": parameters,
           "sampleID": sample_id,
           "taskIndex": node_index(node)['idx'],
           "queueID": queueID,
           "checked": node.is_enabled(),
           "state": state,
           "result": model.result.mca_data
           }

    return res

def _handle_energy_scan(sample_id, node):
    queueID = node._node_id
    enabled, state = get_node_state(queueID)
    parameters = {"element": node.element_symbol,
                  "edge": node.edge,
                  "shape": -1}
    parameters.update(node.path_template.as_dict())
    parameters['path'] = parameters['directory']

    parameters['subdir'] = parameters['path'].\
        split(mxcube.session.get_base_image_directory())[1][1:]

    pt = node.path_template

    parameters['fileName'] = pt.get_image_file_name().\
        replace('%' + ('%sd' % str(pt.precision)), int(pt.precision) * '#')

    parameters['fullPath'] = os.path.join(parameters['path'],
                                          parameters['fileName'])

    res = {"label": "Energy Scan",
           "type": "EnergyScan",
           "parameters": parameters,
           "sampleID": sample_id,
           "taskIndex": node_index(node)['idx'],
           "queueID": queueID,
           "checked": node.is_enabled(),
           "state": state
           }

    return res


def _handle_char(sample_id, node):
    parameters = node.characterisation_parameters.as_dict()
    parameters["shape"] = node.get_point_index()
    refp = _handle_dc(sample_id, node.reference_image_collection)['parameters']

    parameters.update(refp)

    queueID = node._node_id
    enabled, state = get_node_state(queueID)

    originID, task = _handle_diffraction_plan(node)
    res = {"label": "Characterisation",
           "type": "Characterisation",
           "parameters": parameters,
           "checked": node.is_enabled(),
           "sampleID": sample_id,
           "taskIndex": node_index(node)['idx'],
           "queueID": node._node_id,
           "state": state,
           "diffractionPlan": task,
           "diffractionPlanID": originID
           }

    return res

def _handle_diffraction_plan(node):
    model, entry = get_entry(node._node_id)
    originID = model.get_origin()  # char node id
    sample = model.get_parent()  # sample Node
    tasks = []

    if len(model.diffraction_plan) == 0:
        return (-1, {})
    else:
        collections = model.diffraction_plan[0]  # a list of lists

        for col in collections:
            t = _handle_dc(sample._node_id, col)
            if t == None:
                tasks.append({})
                continue

            t['isDiffractionPlan'] = True
            tasks.append(t)

        return (originID, tasks)

    return (-1, {})

def _handle_interleaved(sample_id, node):
    wedges = []

    for child in node.get_children():
        wedges.append(_handle_dc(sample_id, child))

    queueID = node._node_id
    enabled, state = get_node_state(queueID)

    res = {"label": "Interleaved",
           "type": "Interleaved",
           "parameters": {"wedges": wedges,
                          "swNumImages": node.interleave_num_images},
           "checked": node.is_enabled(),
           "sampleID": sample_id,
           "taskIndex": node_index(node)['idx'],
           "queueID": node._node_id,
           "state": state
           }

    return res

def _handle_sample(node):
    location = 'Manual' if node.free_pin_mode else node.loc_str
    enabled, state = get_node_state(node._node_id)
    children_states = []

    for child in node.get_children():
        for _c in child.get_children():
            child_enabled, child_state = get_node_state(_c._node_id)
            children_states.append(child_state)

    if RUNNING in children_states:
        state = RUNNING & SAMPLE_MOUNTED
    elif 3 in children_states:
        state = FAILED & SAMPLE_MOUNTED
    elif all(i == COLLECTED for i in children_states) and len(children_states) > 0:
        state = COLLECTED & SAMPLE_MOUNTED
    else:
        state = UNCOLLECTED

    sample = {node.loc_str: {'sampleID': node.loc_str,
                             'queueID': node._node_id,
                             'code': node.code,
                             'location': location,
                             'sampleName': node.get_name(),
                             'proteinAcronym': node.crystals[0].protein_acronym,
                             'type': 'Sample',
                             'checked': enabled,
                             'state': state,
                             'tasks': queue_to_dict_rec(node)}}

    sample[node.loc_str]["defaultPrefix"] = limsutils.\
        get_default_prefix(sample[node.loc_str], False)

    return sample


def queue_to_dict_rec(node):
    """
    Parses node recursively and builds a representation of the queue based on
    python dictionaries.

    :param TaskNode node: The node to parse
    :returns: A list on the form:
              [ { sampleID_1: sid_1,
                  queueID: qid_1,
                  location: location_n
                  tasks: [task1, ... taskn]},
                .
                .
                .
                { sampleID_N: sid_N,
                  queueID: qid_N,
                  location: location_n,
                  tasks: [task1, ... taskn]} ]
    """
    result = []

    if isinstance(node, list):
        node_list = node
    else:
        node_list = node.get_children()

    for node in node_list:
        if isinstance(node, qmo.Sample):
            if len(result) == 0:
                result = [{'sample_order': []}]

            result.append(_handle_sample(node))
            result[0]['sample_order'].append(node.loc_str)
        elif isinstance(node, qmo.Characterisation):
            sample_id = node.get_parent().get_parent().loc_str
            result.append(_handle_char(sample_id, node))
        elif isinstance(node, qmo.DataCollection):
            sample_id = node_index(node)['sample']
            result.append(_handle_dc(sample_id, node))
        elif isinstance(node, qmo.Workflow):
            sample_id = node.get_parent().get_parent().loc_str
            result.append(_handle_wf(sample_id, node))
        elif isinstance(node, qmo.XRFSpectrum):
            sample_id = node.get_parent().get_parent().loc_str
            result.append(_handle_xrf(sample_id, node))
        elif isinstance(node, qmo.EnergyScan):
            sample_id = node.get_parent().get_parent().loc_str
            result.append(_handle_energy_scan(sample_id, node))
        elif isinstance(node, qmo.TaskGroup) and node.interleave_num_images:
            sample_id = node.get_parent().loc_str
            result.append(_handle_interleaved(sample_id, node))
        else:
            result.extend(queue_to_dict_rec(node))

    return result


def queue_exec_state():
    """
    :returns: The queue execution state, one of QUEUE_STOPPED, QUEUE_PAUSED
              or QUEUE_RUNNING

    """
    state = QUEUE_STOPPED

    if mxcube.queue.queue_hwobj.is_paused():
        state = QUEUE_PAUSED
    elif mxcube.queue.queue_hwobj.is_executing():
        state = QUEUE_RUNNING

    return state


def get_entry(id):
    """
    Retrieves the model and the queue entry for the model node with id <id>

    :param int id: Node id of node to retrieve
    :returns: The tuple model, entry
    :rtype: Tuple
    """
    model = mxcube.queue.get_node(int(id))
    entry = mxcube.queue.queue_hwobj.get_entry_with_model(model)
    return model, entry


def delete_entry(entry):
    """
    Helper function that deletes an entry and its model from the queue
    """
    parent_entry = entry.get_container()
    parent_entry.dequeue(entry)
    model = entry.get_data_model()
    mxcube.queue.del_child(model.get_parent(), model)


def delete_entry_at(item_pos_list):
    current_queue = queue_to_dict()

    for (sid, tindex) in item_pos_list:
        if tindex in ['undefined', None]:
            node_id = current_queue[sid]["queueID"]
            model, entry = get_entry(node_id)
        else:
            node_id = current_queue[sid]["tasks"][int(tindex)]["queueID"]
            model, entry = get_entry(node_id)

            # Get the TaskGroup of the item, there is currently only one
            # task per TaskGroup so we have to remove the entire TaskGroup
            # with its task.
            if not isinstance(entry, qe.TaskGroupQueueEntry):
                entry = entry.get_container()

        delete_entry(entry)


def enable_entry(id_or_qentry, flag):
    """
    Helper function that sets the enabled flag to <flag> for the entry
    and associated model. Takes either the model node id or the QueueEntry
    object.

    Sets enabled flag on both the entry and model.

    :param object id_or_qentry: Node id of model or QueueEntry object
    :param bool flag: True for enabled False for disabled
    """
    if isinstance(id_or_qentry, qe.BaseQueueEntry):
        id_or_qentry.set_enabled(flag)
        id_or_qentry.get_data_model().set_enabled(flag)
    else:
        model, entry = get_entry(id_or_qentry)
        entry.set_enabled(flag)
        model.set_enabled(flag)


def swap_task_entry(sid, ti1, ti2):
    """
    Swaps order of two queue entries in the queue, with the same sample <sid>
    as parent

    :param str sid: Sample id
    :param int ti1: Position of task1 (old position)
    :param int ti2: Position of task2 (new position)
    """
    current_queue = queue_to_dict()

    node_id = current_queue[sid]["queueID"]
    smodel, sentry = get_entry(node_id)

    # Swap the order in the queue model
    ti2_temp_model = smodel.get_children()[ti2]
    smodel._children[ti2] = smodel._children[ti1]
    smodel._children[ti1] = ti2_temp_model

    # Swap queue entry order
    ti2_temp_entry = sentry._queue_entry_list[ti2]
    sentry._queue_entry_list[ti2] = sentry._queue_entry_list[ti1]
    sentry._queue_entry_list[ti1] = ti2_temp_entry


def move_task_entry(sid, ti1, ti2):
    """
    Swaps order of two queue entries in the queue, with the same sample <sid>
    as parent

    :param str sid: Sample id
    :param int ti1: Position of task1 (old position)
    :param int ti2: Position of task2 (new position)
    """
    current_queue = queue_to_dict()

    node_id = current_queue[sid]["queueID"]
    smodel, sentry = get_entry(node_id)

    # Move the order in the queue model
    smodel._children.insert(ti2, smodel._children.pop(ti1))

    # Swap queue entry order
    sentry._queue_entry_list.insert(ti2, sentry._queue_entry_list.pop(ti1))



def queue_add_item(item_list, use_queue_cache=False):
    """
    Adds the queue items in item_list to the queue. The items in the list can
    be either samples and or tasks. Samples are only added if they are not
    already in the queue  and tasks are appended to the end of an
    (already existing) sample. A task is ignored if the sample is not already
    in the queue.

    The items in item_list are dictionaries with the following structure:

    { "type": "Sample | DataCollection | Characterisation",
      "sampleID": sid
      ... task or sample specific data
    }

    Each item (dictionary) describes either a sample or a task.
    """
    global QUEUE_CACHE
    res = None

    if use_queue_cache:
        current_queue = QUEUE_CACHE if QUEUE_CACHE else queue_to_dict()
    else:
        current_queue = queue_to_dict()

    _queue_add_item_rec(item_list, current_queue)

    # Handling interleaved data collections, swap interleave task with
    # the first of the data collections that are used as wedges, and then
    # remove all collections that were used as wedges
    for task in item_list:
        if task["type"] == "Interleaved" and \
           task["parameters"].get("taskIndexList", False):
            current_queue = queue_to_dict()

            sid = task["sampleID"]
            interleaved_tindex = len(current_queue[sid]["tasks"]) - 1

            tindex_list = task["parameters"]["taskIndexList"]
            tindex_list.sort()

            # Swap first "wedge task" and the actual interleaved collection
            # so that the interleaved task is the first task
            swap_task_entry(sid, interleaved_tindex, tindex_list[0])

            # We remove the swapped wedge index from the list, (now pointing
            # at the interleaved collection) and add its new position
            # (last task item) to the list.
            tindex_list = tindex_list[1:]
            tindex_list.append(interleaved_tindex)

            # The delete operation can be done all in one call if we make sure
            # that we remove the items starting from the end (not altering
            # previous indices)
            for ti in reversed(tindex_list):
                delete_entry_at([[sid, int(ti)]])

    if use_queue_cache:
        QUEUE_CACHE = queue_to_dict()
        res = QUEUE_CACHE

    return res

def _queue_add_item_rec(item_list, current_queue):
    """
    Adds the queue items in item_list to the queue. The items in the list can
    be either samples and or tasks. Samples are only added if they are not
    already in the queue  and tasks are appended to the end of an
    (already existing) sample. A task is ignored if the sample is not already
    in the queue.

    The items in item_list are dictionaries with the following structure:

    { "type": "Sample | DataCollection | Characterisation",
      "sampleID": sid
      ... task or sample specific data
    }

    Each item (dictionary) describes either a sample or a task.
    """
    children = []

    for item in item_list:
        item_t = item["type"]
        # If the item a sample, then add it and its tasks. If its not, get the
        # node id for the sample of the new task and append it to the sample
        sample_id = str(item["sampleID"])
        if item_t == "Sample":
            sample_node_id = add_sample(sample_id, item)
            tasks = item.get("tasks")
            
            if tasks:
                children.extend(tasks)
        else:
            sample_node_id = current_queue[sample_id]["queueID"]

        # The item is either a data_collection or a characterisation
        if item_t == "DataCollection":
            add_data_collection(sample_node_id, item)
        elif item_t == "Interleaved":
            add_interleaved(sample_node_id, item)
        elif item_t == "Characterisation":
            add_characterisation(sample_node_id, item)
        elif item_t == "Workflow":
            add_workflow(sample_node_id, item)
        elif item_t == "XRFScan":
            add_xrf_scan(sample_node_id, item)
        elif item_t == "EnergyScan":
            add_energy_scan(sample_node_id, item)

    # Bredth first
    if children:
        _queue_add_item_rec(children, queue_to_dict())


def add_sample(sample_id, item):
    """
    Adds a sample with sample id <sample_id> the queue.

    :param str sample_id: Sample id (often sample changer location)
    :returns: SampleQueueEntry
    """
    # Is the sample with location sample_id already in the queue,
    # in that case, send error response

#    for sampleId, sampleData in queue_to_dict().iteritems():
#        if sampleId == sample_id:
#            msg = "[QUEUE] sample could not be added, already in the queue"
#            raise Exception(msg)

    sample_model = qmo.Sample()
    sample_model.set_origin(ORIGIN_MX3)

    # We should really use sample_id instead of loc_str
    sample_model.loc_str = sample_id
    sample_model.free_pin_mode = item['location'] == 'Manual'

    sample_model.set_name(item['sampleName'])
    sample_model.crystals[0].protein_acronym = item.get('proteinAcronym', '')

    if sample_model.free_pin_mode:
        sample_model.location = (None, sample_id)
    else:
        sample_model.location = tuple(map(int, item['location'].split(':')))

    sample_entry = qe.SampleQueueEntry(Mock(), sample_model)
    sample_entry.set_enabled(True)

    mxcube.queue.add_child(mxcube.queue.get_model_root(), sample_model)
    mxcube.queue.queue_hwobj.enqueue(sample_entry)

    return sample_model._node_id


def set_dc_params(model, entry, task_data, sample_model):
    """
    Helper method that sets the data collection parameters for a DataCollection.

    :param DataCollectionQueueModel: The model to set parameters of
    :param DataCollectionQueueEntry: The queue entry of the model
    :param dict task_data: Dictionary with new parameters
    """
    acq = model.acquisitions[0]
    params = task_data['parameters']
    acq.acquisition_parameters.set_from_dict(params)

    ftype = mxcube.beamline.detector_hwobj.getProperty('file_suffix')
    ftype = ftype if ftype else '.?'

    acq.path_template.set_from_dict(params)
    acq.path_template.suffix = ftype
    acq.path_template.precision = '0' + str(mxcube.session["file_info"].\
        getProperty("precision", 4))

    if params['prefix']:
        acq.path_template.base_prefix = params['prefix']
    else:
        acq.path_template.base_prefix = mxcube.session.\
            get_default_prefix(sample_model, False)

    full_path = os.path.join(mxcube.session.get_base_image_directory(),
                             params.get('subdir', ''))

    acq.path_template.directory = full_path

    process_path = os.path.join(mxcube.session.get_base_process_directory(),
                                params.get('subdir', ''))
    acq.path_template.process_directory = process_path

    # MXCuBE3 specific shape attribute
    model.shape = params["shape"]

    # If there is a centered position associated with this data collection, get
    # the necessary data for the position and pass it to the collection.
    if params["helical"]:
        model.experiment_type = qme.EXPERIMENT_TYPE.HELICAL
        acq2 = qmo.Acquisition()
        model.acquisitions.append(acq2)

        line = mxcube.shapes.get_shape(params["shape"])
        p1, p2 = line.refs
        p1, p2 = mxcube.shapes.get_shape(p1), mxcube.shapes.get_shape(p2)
        cpos1 = p1.get_centred_position()
        cpos2 = p2.get_centred_position()

        acq.acquisition_parameters.centred_position = cpos1
        acq2.acquisition_parameters.centred_position = cpos2

    elif params.get("mesh", False):
        grid = mxcube.shapes.get_shape(params["shape"])
        acq.acquisition_parameters.mesh_range = (grid.width, grid.height)
        mesh_center = mxcube.beamline['default_mesh_values'].getProperty('mesh_center', 'top-left')
        if mesh_center == 'top-left':
            acq.acquisition_parameters.centred_position = grid.get_centred_positions()[0]
        else:
            acq.acquisition_parameters.centred_position = grid.get_centred_positions()[1]
        acq.acquisition_parameters.mesh_steps = grid.get_num_lines()
        acq.acquisition_parameters.num_images = task_data['parameters']['num_images']

        model.experiment_type = qme.EXPERIMENT_TYPE.MESH
        model.set_requires_centring(False)

    elif params["shape"] != -1:
        point = mxcube.shapes.get_shape(params["shape"])
        cpos = point.get_centred_position()
        acq.acquisition_parameters.centred_position = cpos

    acq.path_template.run_number = mxcube.queue.\
        get_next_run_number(acq.path_template)

    model.set_enabled(task_data['checked'])
    entry.set_enabled(task_data['checked'])


def set_wf_params(model, entry, task_data, sample_model):
    """
    Helper method that sets the parameters for a workflow task.

    :param WorkflowQueueModel: The model to set parameters of
    :param GenericWorkflowQueueEntry: The queue entry of the model
    :param dict task_data: Dictionary with new parameters
    """
    params = task_data['parameters']
    model.parameters = params
    model.path_template.set_from_dict(params)
    model.path_template.base_prefix = params['prefix']
    model.path_template.num_files = 0
    model.path_template.precision = '0' +str(mxcube.session["file_info"].\
        getProperty("precision"))

    full_path = os.path.join(mxcube.session.get_base_image_directory(),
                             params.get('subdir', ''))

    model.path_template.directory = full_path

    process_path = os.path.join(mxcube.session.get_base_process_directory(),
                                params.get('subdir', ''))
    model.path_template.process_directory = process_path

    model.set_name("Workflow task")
    model.set_type(params["wfname"])

    beamline_params = {}
    beamline_params['directory'] = model.path_template.directory
    beamline_params['prefix'] = model.path_template.get_prefix()
    beamline_params['run_number'] = model.path_template.run_number
    beamline_params['collection_software'] = 'MXCuBE - 3.0'
    beamline_params['sample_node_id'] = sample_model._node_id
    beamline_params['sample_lims_id'] = sample_model.lims_id
    beamline_params['beamline'] = mxcube.beamline.session_hwobj.beamline_name

    params_list = map(str, list(itertools.chain(*beamline_params.iteritems())))
    params_list.insert(0, params["wfpath"])
    params_list.insert(0, 'modelpath')

    model.params_list = params_list

    model.set_enabled(task_data['checked'])
    entry.set_enabled(task_data['checked'])


def set_char_params(model, entry, task_data, sample_model):
    """
    Helper method that sets the characterisation parameters for a
    Characterisation.

    :param CharacterisationQueueModel: The mode to set parameters of
    :param CharacterisationQueueEntry: The queue entry of the model
    :param dict task_data: Dictionary with new parameters
    """
    params = task_data['parameters']
    set_dc_params(model.reference_image_collection, entry, task_data, sample_model)
    model.characterisation_parameters.set_from_dict(params)

    # Set default characterisation values taken from ednadefaults for
    # those values that are no used in the UI.

    defaults = et.fromstring(mxcube.beamline.getObjectByRole("data_analysis").
                             edna_default_input)

    model.characterisation_parameters.aimed_i_sigma = float(defaults.find(
        ".diffractionPlan/aimedIOverSigmaAtHighestResolution/value").text)

    model.characterisation_parameters.aimed_completness = float(defaults.find(
        ".diffractionPlan/aimedCompleteness/value").text)

    model.characterisation_parameters.aimed_resolution = float(defaults.find(
        ".diffractionPlan/aimedResolution/value").text)

    # MXCuBE3 specific shape attribute
    model.shape = params["shape"]

    model.set_enabled(task_data['checked'])
    entry.set_enabled(task_data['checked'])


def set_xrf_params(model, entry, task_data, sample_model):
    """
    Helper method that sets the xrf scan parameters for a XRF spectrum Scan.

    :param XRFSpectrum QueueModel: The model to set parameters of
    :param XRFSpectrumQueueEntry: The queue entry of the model
    :param dict task_data: Dictionary with new parameters
    """
    params = task_data['parameters']

    # Needs to be taken from XML configuration files if institute dependent
    ftype = "xrf"

    model.path_template.set_from_dict(params)
    model.path_template.suffix = ftype
    model.path_template.precision = '0' + str(mxcube.session["file_info"].\
        getProperty("precision", 4))

    if params['prefix']:
        model.path_template.base_prefix = params['prefix']
    else:
        model.path_template.base_prefix = mxcube.session.\
            get_default_prefix(sample_model, False)

    full_path = os.path.join(mxcube.session.get_base_image_directory(),
                             params.get('subdir', ''))

    model.path_template.directory = full_path

    process_path = os.path.join(mxcube.session.get_base_process_directory(),
                                params.get('subdir', ''))
    model.path_template.process_directory = process_path

    model.path_template.run_number = mxcube.queue.\
        get_next_run_number(model.path_template)

    # Set count time, and if any, other paramters
    model.count_time = params.get("countTime", 0)

    # MXCuBE3 specific shape attribute
    model.shape = params["shape"]

    model.set_enabled(task_data['checked'])
    entry.set_enabled(task_data['checked'])


def set_energy_scan_params(model, entry, task_data, sample_model):
    """
    Helper method that sets the xrf scan parameters for a XRF spectrum Scan.

    :param EnergyScan QueueModel: The model to set parameters of
    :param EnergyScanQueueEntry: The queue entry of the model
    :param dict task_data: Dictionary with new parameters
    """
    params = task_data['parameters']

    # Needs to be taken from XML configuration files if institute dependent
    ftype = "escan"

    model.path_template.set_from_dict(params)
    model.path_template.suffix = ftype
    model.path_template.precision = '0' + str(mxcube.session["file_info"].\
        getProperty("precision", 4))

    if params['prefix']:
        model.path_template.base_prefix = params['prefix']
    else:
        model.path_template.base_prefix = mxcube.session.\
            get_default_prefix(sample_model, False)

    full_path = os.path.join(mxcube.session.get_base_image_directory(),
                             params.get('subdir', ''))

    model.path_template.directory = full_path

    process_path = os.path.join(mxcube.session.get_base_process_directory(),
                                params.get('subdir', ''))
    model.path_template.process_directory = process_path

    model.path_template.run_number = mxcube.queue.\
        get_next_run_number(model.path_template)

    # Set element, and if any, other parameters
    model.element_symbol = params.get("element", "")
    model.edge = params.get("edge", "")

    model.set_enabled(task_data['checked'])
    entry.set_enabled(task_data['checked'])


def _create_dc(task):
    """
    Creates a data collection model and its corresponding queue entry from
    a dict with collection parameters.

    :param dict task: Collection parameters
    :returns: The tuple (model, entry)
    :rtype: Tuple
    """
    dc_model = qmo.DataCollection()
    dc_model.set_origin(ORIGIN_MX3)
    dc_entry = qe.DataCollectionQueueEntry(Mock(), dc_model)

    return dc_model, dc_entry


def _create_wf(task):
    """
    Creates a workflow model and its corresponding queue entry from
    a dict with collection parameters.

    :param dict task: Collection parameters
    :returns: The tuple (model, entry)
    :rtype: Tuple
    """
    dc_model = qmo.Workflow()
    dc_model.set_origin(ORIGIN_MX3)
    dc_entry = qe.GenericWorkflowQueueEntry(Mock(), dc_model)

    return dc_model, dc_entry


def _create_xrf(task):
    """
    Creates a XRFSpectrum model and its corresponding queue entry from
    a dict with collection parameters.

    :param dict task: Collection parameters
    :returns: The tuple (model, entry)
    :rtype: Tuple
    """
    xrf_model = qmo.XRFSpectrum()
    xrf_model.set_origin(ORIGIN_MX3)
    xrf_entry = qe.XRFSpectrumQueueEntry(Mock(), xrf_model)

    return xrf_model, xrf_entry


def _create_energy_scan(task):
    """
    Creates a energy scan model and its corresponding queue entry from
    a dict with collection parameters.

    :param dict task: Collection parameters
    :returns: The tuple (model, entry)
    :rtype: Tuple
    """
    escan_model = qmo.EnergyScan()
    escan_model.set_origin(ORIGIN_MX3)
    escan_entry = qe.EnergyScanQueueEntry(Mock(), escan_model)

    return escan_model, escan_entry


def add_characterisation(node_id, task):
    """
    Adds a data characterisation task to the sample with id: <id>

    :param int id: id of the sample to which the task belongs
    :param dict task: Task data (parameters)

    :returns: The queue id of the Data collection
    :rtype: int
    """
    sample_model, sample_entry = get_entry(node_id)
    params = task['parameters']

    refdc_model, refdc_entry = _create_dc(task)
    refdc_model.acquisitions[0].path_template.reference_image_prefix = 'ref'
    refdc_model.set_name('refdc')
    char_params = qmo.CharacterisationParameters().set_from_dict(params)

    char_model = qmo.Characterisation(refdc_model, char_params)

    char_model.set_origin(ORIGIN_MX3)
    char_entry = qe.CharacterisationGroupQueueEntry(Mock(), char_model)
    char_entry.queue_model_hwobj = mxcube.queue
    # Set the characterisation and reference collection parameters
    set_char_params(char_model, char_entry, task, sample_model)

    # the default value is True, here we adapt to mxcube3 needs
    char_model.auto_add_diff_plan = mxcube.AUTO_ADD_DIFFPLAN
    char_entry.auto_add_diff_plan = mxcube.AUTO_ADD_DIFFPLAN

    # A characterisation has two TaskGroups one for the characterisation itself
    # and its reference collection and one for the resulting diffraction plans.
    # But we only create a reference group if there is a result !
    refgroup_model = qmo.TaskGroup()
    refgroup_model.set_origin(ORIGIN_MX3)

    mxcube.queue.add_child(sample_model, refgroup_model)
    mxcube.queue.add_child(refgroup_model, char_model)
    refgroup_entry = qe.TaskGroupQueueEntry(Mock(), refgroup_model)

    refgroup_entry.set_enabled(True)
    sample_entry.enqueue(refgroup_entry)
    refgroup_entry.enqueue(char_entry)

    char_model.set_enabled(task['checked'])
    char_entry.set_enabled(task['checked'])

    return char_model._node_id


def add_data_collection(node_id, task):
    """
    Adds a data collection task to the sample with id: <id>

    :param int id: id of the sample to which the task belongs
    :param dict task: task data

    :returns: The queue id of the data collection
    :rtype: int
    """
    sample_model, sample_entry = get_entry(node_id)
    dc_model, dc_entry = _create_dc(task)
    set_dc_params(dc_model, dc_entry, task, sample_model)

    pt = dc_model.acquisitions[0].path_template

    if mxcube.queue.check_for_path_collisions(pt):
        msg = "[QUEUE] data collection could not be added to sample: "
        msg += "path collision"
        raise Exception(msg)

    group_model = qmo.TaskGroup()
    group_model.set_origin(ORIGIN_MX3)
    group_model.set_enabled(True)
    mxcube.queue.add_child(sample_model, group_model)
    mxcube.queue.add_child(group_model, dc_model)

    group_entry = qe.TaskGroupQueueEntry(Mock(), group_model)
    group_entry.set_enabled(True)
    sample_entry.enqueue(group_entry)
    group_entry.enqueue(dc_entry)

    return dc_model._node_id


def add_workflow(node_id, task):
    """
    Adds a worklfow task to the sample with id: <id>

    :param int id: id of the sample to which the task belongs
    :param dict task: task data

    :returns: The queue id of the data collection
    :rtype: int
    """
    sample_model, sample_entry = get_entry(node_id)
    wf_model, dc_entry = _create_wf(task)
    set_wf_params(wf_model, dc_entry, task, sample_model)

    pt = wf_model.path_template

    if mxcube.queue.check_for_path_collisions(pt):
        msg = "[QUEUE] data collection could not be added to sample: "
        msg += "path collision"
        raise Exception(msg)

    group_model = qmo.TaskGroup()
    group_model.set_origin(ORIGIN_MX3)
    group_model.set_enabled(True)
    mxcube.queue.add_child(sample_model, group_model)
    mxcube.queue.add_child(group_model, wf_model)

    group_entry = qe.TaskGroupQueueEntry(Mock(), group_model)
    group_entry.set_enabled(True)
    sample_entry.enqueue(group_entry)
    group_entry.enqueue(dc_entry)

    return wf_model._node_id


def add_interleaved(node_id, task):
    """
    Adds a interleaved data collection task to the sample with id: <id>

    :param int id: id of the sample to which the task belongs
    :param dict task: task data

    :returns: The queue id of the data collection
    :rtype: int
    """
    sample_model, sample_entry = get_entry(node_id)

    group_model = qmo.TaskGroup()
    group_model.set_origin(ORIGIN_MX3)
    group_model.set_enabled(True)
    group_model.interleave_num_images = task['parameters']['swNumImages']

    group_entry = qe.TaskGroupQueueEntry(Mock(), group_model)
    group_entry.set_enabled(True)
    sample_entry.enqueue(group_entry)
    mxcube.queue.add_child(sample_model, group_model)

    wc = 0

    for wedge in task['parameters']['wedges']:
        wc = wc + 1
        dc_model, dc_entry = _create_dc(wedge)
        set_dc_params(dc_model, dc_entry, wedge, sample_model)
        dc_model.acquisitions[0].path_template.wedge_prefix = "wedge-%s" % wc
        mxcube.queue.add_child(group_model, dc_model)
        group_entry.enqueue(dc_entry)

    return group_model._node_id


def add_xrf_scan(node_id, task):
    """
    Adds a XRF Scan task to the sample with id: <id>

    :param int id: id of the sample to which the task belongs
    :param dict task: task data

    :returns: The queue id of the data collection
    :rtype: int
    """
    sample_model, sample_entry = get_entry(node_id)
    xrf_model, xrf_entry = _create_xrf(task)
    set_xrf_params(xrf_model, xrf_entry, task, sample_model)

    pt = xrf_model.path_template

    if mxcube.queue.check_for_path_collisions(pt):
        msg = "[QUEUE] data collection could not be added to sample: "
        msg += "path collision"
        raise Exception(msg)

    group_model = qmo.TaskGroup()
    group_model.set_origin(ORIGIN_MX3)
    group_model.set_enabled(True)
    mxcube.queue.add_child(sample_model, group_model)
    mxcube.queue.add_child(group_model, xrf_model)

    group_entry = qe.TaskGroupQueueEntry(Mock(), group_model)
    group_entry.set_enabled(True)
    sample_entry.enqueue(group_entry)
    group_entry.enqueue(xrf_entry)

    return xrf_model._node_id


def add_energy_scan(node_id, task):
    """
    Adds a energy scan task to the sample with id: <id>

    :param int id: id of the sample to which the task belongs
    :param dict task: task data

    :returns: The queue id of the data collection
    :rtype: int
    """
    sample_model, sample_entry = get_entry(node_id)
    escan_model, escan_entry = _create_energy_scan(task)
    set_energy_scan_params(escan_model, escan_entry, task, sample_model)

    pt = escan_model.path_template

    if mxcube.queue.check_for_path_collisions(pt):
        msg = "[QUEUE] data collection could not be added to sample: "
        msg += "path collision"
        raise Exception(msg)

    group_model = qmo.TaskGroup()
    group_model.set_origin(ORIGIN_MX3)
    group_model.set_enabled(True)
    mxcube.queue.add_child(sample_model, group_model)
    mxcube.queue.add_child(group_model, escan_model)

    group_entry = qe.TaskGroupQueueEntry(Mock(), group_model)
    group_entry.set_enabled(True)
    sample_entry.enqueue(group_entry)
    group_entry.enqueue(escan_entry)

    return escan_model._node_id


def new_queue():
    """
    Creates a new queue
    :returns: MxCuBE QueueModel Object
    """
    queue = pickle.loads(mxcube.empty_queue)
    queue.diffraction_plan = {}

    init_signals(queue)
    mxcube.xml_rpc_server.queue_hwobj = queue.queue_hwobj
    mxcube.xml_rpc_server.queue_model_hwobj = queue
    return queue


def save_queue(session, redis=redis.Redis()):
    """
    Saves the current mxcube queue (mxcube.queue) into a redis database.
    The queue that is saved is the pickled result returned by queue_to_dict

    :param session: Session to save queue for
    :param redis: Redis database

    """
    proposal_id = Utils._proposal_id(session)

    if proposal_id is not None:
        # List of samples dicts (containing tasks) sample and tasks have same
        # order as the in queue HO
        queue = queue_to_dict(mxcube.queue.get_model_root())
        redis.set("mxcube:queue:%d" % proposal_id, pickle.dumps(queue))


def load_queue(session, redis=redis.Redis()):
    """
    Loads the queue belonging to session <session> into redis db <redis>

    :param session: Session for queue to load
    :param redis: Redis database
    """
    proposal_id = Utils._proposal_id(session)

    if proposal_id is not None:
        serialized_queue = redis.get("mxcube:queue:%d" % proposal_id)
        queue = pickle.loads(serialized_queue)
        load_queue_from_dict(queue)


def queue_model_child_added(parent, child):
    """
    Listen to the addition of elements to the queue model ('child_added').
    Add the corresponding entries to the queue if they are not already
    added. Handels for instance the addition of referance collections for
    characterisations and workflows.
    """
    parent_model, parent_entry = get_entry(parent._node_id)
    child_model, child_entry = get_entry(child._node_id)

    # Origin is ORIGIN_MX3 if task comes from MXCuBE-3
    if child_model.get_origin() != ORIGIN_MX3:
        if isinstance(child, qmo.DataCollection):
            dc_entry = qe.DataCollectionQueueEntry(Mock(), child)

            enable_entry(dc_entry, True)
            enable_entry(parent_entry, True)
            parent_entry.enqueue(dc_entry)
            sample = parent.get_parent()

            task = _handle_dc(sample._node_id, child)
            socketio.emit('add_task', {"tasks": [task]}, namespace='/hwr')

        elif isinstance(child, qmo.TaskGroup):
            dcg_entry = qe.TaskGroupQueueEntry(Mock(), child)
            enable_entry(dcg_entry, True)
            parent_entry.enqueue(dcg_entry)


def queue_model_diff_plan_available(char, index, collection):
    if isinstance(collection, qmo.DataCollection):
        if collection.get_origin():
            origin_model, origin_entry = get_entry(collection.get_origin())
        collection.set_enabled(False)
        dcg_model = char.get_parent()
        sample = dcg_model.get_parent()
        task = _handle_dc(sample._node_id, collection)
        task.update({'isDiffractionPlan': True, 'originID': origin_model._node_id})
        socketio.emit('add_diff_plan', {"tasks": [task]}, namespace='/hwr')

def set_auto_add_diffplan(autoadd, current_sample=None):
    """
    Sets auto mount next flag, automatically mount next sample in queue
    (True) or wait for user (False)

    :param bool automount: True auto-mount, False wait for user
    """
    mxcube.AUTO_ADD_DIFFPLAN = autoadd
    current_queue = queue_to_dict()
    current_queue.pop('sample_order')
    sampleIDs = current_queue.keys()
    for sample in sampleIDs:
        # this would be a sample
        tasks = current_queue[sample]['tasks']
        for t in tasks:
            if t['type'] == 'Characterisation':
                model, entry =  get_entry(t['queueID'])
                entry.auto_add_diff_plan = autoadd

def execute_entry_with_id(sid, tindex=None):
    """
    Execute the entry at position (sampleID, task index) in queue

    :param str sid: sampleID
    :param int tindex: task index of task within sample with id sampleID
    """
    current_queue = queue_to_dict()
    mxcube.queue.queue_hwobj.set_pause(False)

    if tindex in ['undefined', 'None', 'null', None]:
        node_id = current_queue[sid]["queueID"]

        enable_sample_entries(current_queue["sample_order"], False)
        enable_sample_entries([sid], True)

        # The queue ignores empty samples (so does not run the mount defined by
        # the sample task), so in order function as expected; just mount the
        # sample
        if (not len(current_queue[sid]["tasks"])) and \
           sid != scutils.get_current_sample():

            scutils.mount_sample_clean_up(current_queue[sid])

        mxcube.queue.queue_hwobj.execute()
    else:
        node_id = current_queue[sid]["tasks"][int(tindex)]["queueID"]

        node, entry = get_entry(node_id)
	# in order to fill lims data, we execute first the parent (group_id missing)
	parent_id = node.get_parent()._node_id
	
        node, entry = get_entry(parent_id)

        mxcube.queue.queue_hwobj._running = True

        mxcube.queue.queue_hwobj._is_stopped = False
        mxcube.queue.queue_hwobj._set_in_queue_flag()
        try:
            mxcube.queue.queue_hwobj.execute_entry(entry)
        except:
            mxcube.queue.queue_hwobj.emit('queue_execution_failed', (None,))
        finally:
            mxcube.queue.queue_hwobj._running = False
            mxcube.queue.queue_hwobj.emit('queue_stopped', (None,))


def init_signals(queue):
    """
    Initialize queue hwobj related signals.
    """
    import signals

    mxcube.collect.connect(mxcube.collect, "collectStarted",
                           signals.collect_started)
    mxcube.collect.connect(mxcube.collect, 'collectOscillationStarted',
                           signals.collect_oscillation_started)
    mxcube.collect.connect(mxcube.collect, 'collectOscillationFailed',
                           signals.collect_oscillation_failed)
    mxcube.collect.connect(mxcube.collect, 'collectImageTaken',
                           signals.collect_image_taken)

    mxcube.collect.connect(mxcube.collect, 'collectOscillationFinished',
                           signals.collect_oscillation_finished)

    queue.connect(queue, 'child_added', queue_model_child_added)

    queue.connect(queue, 'diff_plan_available', queue_model_diff_plan_available)

    queue.queue_hwobj.connect("queue_execute_started",
                              signals.queue_execution_started)

    queue.queue_hwobj.connect("queue_execution_finished",
                              signals.queue_execution_finished)

    queue.queue_hwobj.connect("queue_stopped",
                              signals.queue_execution_finished)

    queue.queue_hwobj.connect("queue_execute_entry_finished",
                              signals.queue_execution_entry_finished)

    queue.queue_hwobj.connect("collectEnded", signals.collect_ended)

    queue.queue_hwobj.connect("queue_interleaved_started",
                              signals.queue_interleaved_started)

    queue.queue_hwobj.connect("queue_interleaved_finished",
                              signals.queue_interleaved_finished)

    queue.queue_hwobj.connect('queue_interleaved_sw_done',
                              signals.queue_interleaved_sw_done)


def enable_sample_entries(sample_id_list, flag):
    current_queue = queue_to_dict()

    for sample_id in sample_id_list:
        sample_data = current_queue[sample_id]
        enable_entry(sample_data["queueID"], flag)


def set_auto_mount_sample(automount, current_sample=None):
    """
    Sets auto mount next flag, automatically mount next sample in queue
    (True) or wait for user (False)

    :param bool automount: True auto-mount, False wait for user
    """
    mxcube.AUTO_MOUNT_SAMPLE = automount
    current_queue = queue_to_dict()

    sample = current_sample if current_sample else scutils.get_current_sample()

    # If automount next is off, that is do not mount and run next
    # sample, disable all entries except the current one
    # If automount next is on, enable all
    enable_sample_entries(current_queue["sample_order"], automount)

    # No automount, enable the current entry if any
    if not automount and sample:
        enable_sample_entries([sample], True)


def get_auto_mount_sample():
    """
    :returns: Returns auto mount flag
    :rtype: bool
    """
    return mxcube.AUTO_MOUNT_SAMPLE


def get_task_progress(node, pdata):
    progress = 0

    if node.is_executed():
        progress = 1
    elif is_interleaved(node):
        progress = (pdata["current_idx"] + 1) * pdata["sw_size"] / float(pdata["nitems"] * pdata["sw_size"])
    elif isinstance(node, qmo.Characterisation):
        dc = node.reference_image_collection
        total = float(dc.acquisitions[0].acquisition_parameters.num_images) * 2
        progress = pdata / total
    else:
        total = float(node.acquisitions[0].acquisition_parameters.num_images)
        progress = pdata / total

    return progress


def is_interleaved(node):
    return hasattr(node, "interleave_num_images") and \
        node.interleave_num_images > 0
