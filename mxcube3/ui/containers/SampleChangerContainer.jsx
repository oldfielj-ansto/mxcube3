import React from 'react';
import { bindActionCreators } from 'redux';
import { connect } from 'react-redux';

import { sampleChangerSelect, loadSample, unloadSample, scan
} from '../actions/sample_changer';

import SampleChanger from '../components/SampleChanger/SampleChanger';

class SampleChangerContainer extends React.Component {
  render() {
    return  (<SampleChanger
      select={this.props.select}
      load={this.props.loadSample}
      unload={this.props.unloadSample}
      scan={this.props.scan}
      contents={this.props.contents}>
    </SampleChanger>);
  }
}

function mapStateToProps(state) {
  return {
    contents: state.sampleChanger.contents
  };
}

function mapDispatchToProps(dispatch) {
  return {
    select: (address) => dispatch(sampleChangerSelect(address)),
    loadSample: (address) => dispatch(loadSample(address)),
    unloadSample: (address) => dispatch(unloadSample(address)),
    scan: (container) => dispatch(sampleChangerScan(container))
  };
}

export default connect(
  mapStateToProps,
  mapDispatchToProps
)(SampleChangerContainer);

