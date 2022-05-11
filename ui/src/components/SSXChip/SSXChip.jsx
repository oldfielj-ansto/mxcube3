import React from 'react';
import { Menu, Item, Separator, Submenu, MenuProvider, contextMenu } from 'react-contexify';
import 'fabric';
import './ssxchipcontrol.css';
import "react-contexify/dist/ReactContexify.css";

const fabric = window.fabric;

const ChipContextMenu = (props) => {
  return (
    <Menu  id="chip-context-menu">
      <li role="heading" aria-level="2" className="dropdown-header">
        <b>
          Chip
        </b>
      </li>
      <Separator />
      <Item
        id="moveto"
        data={{}}
        onClick={props.onMoveTo}
      >
        Move to
      </Item>
      <Item
        id="addtask"
        data={{}}
        onClick={props.onAddTask}
      >
        Add to queue
      </Item>
    </Menu>
  );
}

export default class SSXChip extends React.Component {
  constructor(props) {
    super(props);
    this.canvasRef = React.createRef();
    this.detailCanvasRef = React.createRef();
    this.fc = null;
    this.detailCanvas = null
  }

  showContextMenu(event, selection) {
    contextMenu.show({
      id: "chip-context-menu",
      event: event.e,
      position: {
        x: event.e.offsetX + 15,
        y: event.e.offsetY + 55,
      },
      props: {
        selection: selection
      },
    });
  }

  renderChip(
    chipSizeX,
    chipSizeY,
    rows,
    cols,
    blockSizeX,
    blockSizeY,
    spacing,
    offset,
  ) {
    const objects = [];

    objects.push(
      new fabric.Rect({
        top: 0,
        left: 0 ,
        width: chipSizeX,
        height: chipSizeY,
        selectable: false,
        hasControls: false,
        borderColor: "#fff",
        lockMovementX: true,
        lockMovementY: true,
        lockScalingX: true,
        lockScalingY: true,
        lockSkewingX: true,
        lockSkewingY: true,
        lockRotation: true,
        hoverCursor: "arrow",
        type: "CHIP",
        objectIndex: []
      })
    );

    for (let ri=0; ri < rows; ri++) {
      for(let ci=0; ci < cols; ci++) {
        objects.push(
          new fabric.Rect({
            top: ri*(blockSizeY+spacing) + offset,
            left: (ci*(blockSizeX+spacing)) + offset,
            width: blockSizeX,
            height: blockSizeY,
            fill: '#f55',
            objectCaching: false,
            hasControls: false,
            borderColor: "#fff",
            lockMovementX: true,
            lockMovementY: true,
            lockScalingX: true,
            lockScalingY: true,
            lockSkewingX: true,
            lockSkewingY: true,
            lockRotation: true,
            hoverCursor: "pointer",
            type: "BLOCK",
            objectIndex: [ri, ci]
          })
        );
      }
    }

    return objects;
  }

  componentDidMount() {
    const canvas = new fabric.Canvas('chip-canvas', {
      width: 415,//this.canvasRef.current.clientWidth,
      height: 415, //this.canvasRef.current.clientHeight,
      backgroundColor: "#CCC",
      preserveObjectStacking: true,
      altSelectionKey: "ctrlKey",
      selectionKey: 'ctrlKey',
      fireRightClick: true,
      stopContextMenu: true,
    });

    const detailCanvas = new fabric.StaticCanvas('chip-detail-canvas', {
      width: 415,//this.canvasRef.current.clientWidth,
      height: 415, //this.canvasRef.current.clientHeight,
      backgroundColor: "#CCC",
      preserveObjectStacking: true,
      altSelectionKey: "ctrlKey",
      selectionKey: 'ctrlKey',
      fireRightClick: true,
      stopContextMenu: true,
      renderOnAddRemove: false,
    });

    this.fc = canvas;
    this.detailCanvas = detailCanvas

    this.fc.on('mouse:down', (event) => {
      const object = canvas.findTarget(event.e);

      if(event.button === 3) {
          let selection = [];

          if (object.type === "BLOCK") {
            selection.push([object.objectIndex]);
          }

          if (object.type === "activeSelection") {
            selection = object._objects.map((o) => o.objectIndex);
          }

          if (selection.length > 0) {
            this.fc.setActiveObject(object);
            this.fc.requestRenderAll();
            this.showContextMenu(event, selection);
          }
      }
    });

    this.fc.on('selection:created', ({ selected, target }) => {
      if (selected.some(obj => obj.lockMovementX)) {
        target.lockMovementX = true;
      }
        if (selected.some(obj => obj.lockMovementY)) {
        target.lockMovementY = true;
      }
    });

    this.fc.on('selection:updated', ({ selected, target }) => {
      if (selected.some(obj => obj.lockMovementX)) {
        target.lockMovementX = true;
      }
        if (selected.some(obj => obj.lockMovementY)) {
        target.lockMovementY = true;
      }
    });

    this.fc.on('mouse:dblclick', (event) => {
      const object = canvas.findTarget(event.e);
      console.log(object.type);
      console.log("move to:" + object.objectIndex);
      console.log("double click")
    });
    this.fc.add(...this.renderChip(
      415, 415, 10, 10, 25, 25, 15, 15
    ));
    this.fc.requestRenderAll();

    this.detailCanvas.add(...this.renderChip(
      415, 415, 25, 25, 2.5, 2.5, 15, 15
    ));
    this.detailCanvas.renderAll();
  }

  render() { 
    return (
      <div className="chip-container">
        <div className="chip-canvas-container">
          <canvas
            id="chip-canvas" 
            ref={this.canvasRef}
          />
          <ChipContextMenu {...this.props}/>
        </div>
        <div className="chip-detial-canvas-container">
          <canvas
            id="chip-detail-canvas"
            ref={this.detailCanvasRef}
          />
        </div>
    </div>
    );
  }
}
