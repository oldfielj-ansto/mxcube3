import React from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';

import { Container, Row, Col } from 'react-bootstrap';

import {
  select,
  loadSample,
  unloadSample,
  scan,
  abort,
  sendCommand,
  refresh,
  selectWell,
  setPlate,
  selectDrop,
} from '../actions/sampleChanger';

import {
  abort as haAbort,
  sendCommand as haSendCommand,
  refresh as haRefresh,
  harvestCrystal,
  harvestAndLoadCrystal,
  calibratePin as haCalibratePin,
  validateCalibration as haValidateCalibration,
  sendDataCollectionToCrims,
} from '../actions/harvester';

import { showErrorPanel } from '../actions/general';

import { syncWithCrims } from '../actions/sampleGrid';

import { executeCommand } from '../actions/beamline';

import SampleChanger from '../components/Equipment/SampleChanger';
import SampleChangerMaintenance from '../components/Equipment/SampleChangerMaintenance';

import PlateManipulator from '../components/Equipment/PlateManipulator';
import PlateManipulatorMaintenance from '../components/Equipment/PlateManipulatorMaintenance';

import Harvester from '../components/Equipment/Harvester';
import HarvesterMaintenance from '../components/Equipment/HarvesterMaintenance';

import GenericEquipment from '../components/Equipment/GenericEquipment';
import GenericEquipmentControl from '../components/Equipment/GenericEquipmentControl';

class EquipmentContainer extends React.Component {
  render() {
    return (
      <Container fluid className="mt-3">
        <Row className="d-flex">
          <Col sm={12}>
            <GenericEquipment
              state={this.props.sampleChangerState}
              name={this.props.contents?.name}
              CollapseOpen
            >
              {this.props.contents.name === 'PlateManipulator' ? (
                <Row className="row">
                  <Col sm={6}>
                    <PlateManipulator
                      contents={this.props.contents}
                      loadedSample={this.props.loadedSample}
                      select={this.props.select}
                      load={this.props.loadSample}
                      sendCommand={this.props.sendCommand}
                      refresh={this.props.refresh}
                      inPopover={false}
                      plates={this.props.plateGrid}
                      plateIndex={this.props.plateIndex}
                      selectedRow={this.props.selectedRow}
                      selectedCol={this.props.selectedCol}
                      selectedDrop={this.props.selectedDrop}
                      setPlate={this.props.setPlate}
                      selectWell={this.props.selectWell}
                      selectDrop={this.props.selectDrop}
                      crystalList={this.props.crystalList}
                      syncSamplesCrims={this.props.syncSamplesCrims}
                      showErrorPanel={this.props.showErrorPanel}
                      global_state={this.props.global_state}
                      state={this.props.sampleChangerState}
                    />
                  </Col>
                  <Col sm={6}>
                    <PlateManipulatorMaintenance
                      commands={this.props.commands}
                      global_state={this.props.global_state}
                      commands_state={this.props.commands_state}
                      message={this.props.message}
                      sendCommand={this.props.sendCommand}
                      contents={this.props.contents}
                    />
                  </Col>
                </Row>
              ) : (
                <Row className="row">
                  <Col sm={6}>
                    <SampleChanger
                      state={this.props.sampleChangerState}
                      loadedSample={this.props.loadedSample}
                      select={this.props.select}
                      load={this.props.loadSample}
                      unload={this.props.unloadSample}
                      abort={this.props.abort}
                      scan={this.props.scan}
                      contents={this.props.contents}
                      refresh={this.props.refresh}
                    />
                  </Col>
                  <Col sm={6}>
                    <SampleChangerMaintenance
                      commands={this.props.commands}
                      global_state={this.props.global_state}
                      commands_state={this.props.commands_state}
                      message={this.props.message}
                      sendCommand={this.props.sendCommand}
                    />
                  </Col>
                </Row>
              )}
            </GenericEquipment>
            {this.props.haContents.use_harvester ? (
              <GenericEquipment
                state={this.props.haState}
                name={this.props.haContents?.name}
                CollapseOpen
              >
                <Row className="row">
                  <Col sm={9}>
                    <Harvester
                      state={this.props.haState}
                      harvestCrystal={this.props.harvestCrystal}
                      harvestAndLoadCrystal={this.props.harvestAndLoadCrystal}
                      abort={this.props.haAbort}
                      contents={this.props.haContents}
                      handleRefresh={this.props.haRefresh}
                    />
                  </Col>
                  <Col sm={3}>
                    <HarvesterMaintenance
                      contents={this.props.haContents}
                      commands={this.props.haCommands}
                      global_state={this.props.haGlobal_state}
                      commands_state={this.props.commands_state}
                      message={this.props.haMessage}
                      sendCommand={this.props.haSendCommand}
                      calibratePin={this.props.haCalibratePin}
                      sendDCToCrims={this.props.sendDataCollectionToCrims}
                      validateCalibration={this.props.haValidateCalibration}
                    />
                  </Col>
                </Row>
              </GenericEquipment>
            ) : null}
            <Row>
              <Col sm={12}>
                {Object.entries(this.props.beamline.hardwareObjects).map(
                  ([key, value]) => {
                    const obj = this.props.beamline.hardwareObjects[key];
                    if (
                      !Array.isArray(obj.commands) &&
                      Object.values(obj.commands).length > 0
                    ) {
                      return (
                        <GenericEquipmentControl
                          equipment={obj}
                          executeCommand={this.props.executeCommand}
                          key={key}
                        />
                      );
                    }
                    return null;
                  },
                )}
              </Col>
            </Row>
          </Col>
        </Row>
      </Container>
    );
  }
}

function mapStateToProps(state) {
  return {
    contents: state.sampleChanger.contents,
    sampleChangerState: state.sampleChanger.state,
    loadedSample: state.sampleChanger.loadedSample,

    plateGrid: state.sampleChanger.plateGrid,
    plateIndex: state.sampleChanger.currentPlateIndex,
    selectedRow: state.sampleChanger.selectedRow,
    selectedCol: state.sampleChanger.selectedCol,
    selectedDrop: state.sampleChanger.selectedDrop,
    crystalList: state.sampleGrid.crystalList,

    commands: state.sampleChangerMaintenance.commands,
    commands_state: state.sampleChangerMaintenance.commands_state,
    global_state: state.sampleChangerMaintenance.global_state,
    message: state.sampleChangerMaintenance.message,
    beamline: state.beamline,

    haContents: state.harvester.contents,
    haState: state.harvester.state,
    haCommands: state.harvesterMaintenance.commands,
    haCommands_state: state.harvesterMaintenance.commands_state,
    haGlobal_state: state.harvesterMaintenance.global_state,
    haMessage: state.harvesterMaintenance.message,
  };
}

function mapDispatchToProps(dispatch) {
  return {
    select: (address) => dispatch(select(address)),
    loadSample: (address) => dispatch(loadSample(address)),
    unloadSample: (address) => dispatch(unloadSample(address)),
    scan: (container) => dispatch(scan(container)),
    refresh: () => dispatch(refresh()),
    abort: () => dispatch(abort()),
    sendCommand: (cmd, args) => dispatch(sendCommand(cmd, args)),
    executeCommand: bindActionCreators(executeCommand, dispatch),
    showErrorPanel: bindActionCreators(showErrorPanel, dispatch),
    selectWell: (row, col) => dispatch(selectWell(row, col)),
    setPlate: (address) => dispatch(setPlate(address)),
    selectDrop: (address) => dispatch(selectDrop(address)),
    syncSamplesCrims: () => dispatch(syncWithCrims()),

    harvestCrystal: (address) => dispatch(harvestCrystal(address)),
    harvestAndLoadCrystal: (address) =>
      dispatch(harvestAndLoadCrystal(address)),
    haCalibratePin: () => dispatch(haCalibratePin()),
    sendDataCollectionToCrims: () => dispatch(sendDataCollectionToCrims()),
    haValidateCalibration: (validated) =>
      dispatch(haValidateCalibration(validated)),
    haRefresh: () => dispatch(haRefresh()),
    haAbort: () => dispatch(haAbort()),
    haSendCommand: (cmd, args) => dispatch(haSendCommand(cmd, args)),
  };
}

export default connect(mapStateToProps, mapDispatchToProps)(EquipmentContainer);
