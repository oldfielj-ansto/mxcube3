import React from 'react';
import 'fabric';
import {
  Button,
  OverlayTrigger,
  Popover,
  FormControl
} from 'react-bootstrap';
import './ssxchipcontrol.css';
import SSXChip from './SSXChip';

const fabric = window.fabric;

export default class SSXChipControl extends React.Component {
  constructor(props) {
    super(props);
  }

  renderChip() {
    return (
      <Popover id="test" title={<b>Chip</b>}>
        <SSXChip />
      </Popover>
    );
  }


  render() {
    return (
      <div style={{marginBottom: '1em'}}>
        <span className='chip-title'>Chip (Diamond Chip):</span>
        <OverlayTrigger
          trigger="click"
          rootClose
          placement="right"
          overlay={this.renderChip()}
        >
          <Button>
            <i className="fas fa-braille" /> Navigate
          </Button>
        </OverlayTrigger>
      </div>
    );
  }
}
