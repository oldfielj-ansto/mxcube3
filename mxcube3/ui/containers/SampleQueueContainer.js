import React from 'react';
import { bindActionCreators } from 'redux';
import { connect } from 'react-redux';
import CurrentTree from '../components/SampleQueue/CurrentTree';
import TodoTree from '../components/SampleQueue/TodoTree';
import QueueControl from '../components/SampleQueue/QueueControl';
import * as QueueActions from '../actions/queue';
import * as SampleViewActions from '../actions/sampleview';
import { showTaskForm } from '../actions/taskForm';
import { DragDropContext as dragDropContext } from 'react-dnd';
import HTML5Backend from 'react-dnd-html5-backend';
import { Nav, NavItem } from 'react-bootstrap';


function mapStateToProps(state) {
  return {
    searchString: state.queue.searchString,
    current: state.queue.current,
    visibleList: state.queue.visibleList,
    todo: state.queue.todo,
    queueStatus: state.queue.queueStatus,
    history: state.queue.history,
    queue: state.queue.queue,
    sampleInformation: state.queue.sampleList,
    checked: state.queue.checked,
    select_all: state.queue.selectAll,
    mounted: state.queue.manualMount.set,
    rootPath: state.queue.rootPath,
    displayData: state.queueGUI.displayData,
    manualMount: state.queue.manualMount
  };
}


function mapDispatchToProps(dispatch) {
  return {
    queueActions: bindActionCreators(QueueActions, dispatch),
    sampleViewActions: bindActionCreators(SampleViewActions, dispatch),
    showForm: bindActionCreators(showTaskForm, dispatch)
  };
}


@dragDropContext(HTML5Backend)
@connect(mapStateToProps, mapDispatchToProps)
export default class SampleQueueContainer extends React.Component {

  constructor(props) {
    super(props);
    this.handleSelect = this.handleSelect.bind(this);
  }

  handleSelect(selectedKey) {
    this.props.queueActions.showList(selectedKey);
  }


  render() {
    const {
      checked,
      todo,
      current,
      history,
      sampleInformation,
      queue,
      showForm,
      queueStatus,
      rootPath,
      displayData,
      manualMount,
      visibleList
    } = this.props;
    const {
      sendToggleCheckBox,
      sendRunSample,
      sendRunQueue,
      sendPauseQueue,
      sendUnpauseQueue,
      sendStopQueue,
      sendUnmountSample,
      changeTaskOrderAction,
      collapseTask,
      collapseSample,
      deleteTask,
      sendMountSample
    } = this.props.queueActions;

    return (
      <div style={ { display: 'flex', flexDirection: 'column', width: '100%' } }>
                <QueueControl
                  historyLength={history.length}
                  todoLength={todo.length}
                  currentNode={current.node}
                  queueStatus={queueStatus}
                  runQueue={sendRunQueue}
                  stopQueue={sendStopQueue}
                />
              <div className="m-tree queue-body">
                <Nav
                  bsStyle="tabs"
                  justified
                  activeKey={visibleList}
                  onSelect={this.handleSelect}
                >
                  <NavItem eventKey={'current'}>Current</NavItem>
                  <NavItem eventKey={'todo'}>Upcoming</NavItem>
                </Nav>
                <CurrentTree
                  changeOrder={changeTaskOrder}
                  show={visibleList === 'current'}
                  mounted={current.node}
                  sampleInformation={sampleInformation}
                  queue={queue}
                  toggleCheckBox={sendToggleCheckBox}
                  checked={checked}
                  deleteTask={deleteTask}
                  run={sendRunSample}
                  pause={sendPauseQueue}
                  unpause={sendUnpauseQueue}
                  stop={sendStopQueue}
                  showForm={showForm}
                  unmount={sendUnmountSample}
                  queueStatus={queueStatus}
                  rootPath={rootPath}
                  collapseTask={collapseTask}
                  displayData={displayData}
                  manualMount={manualMount}
                  mount={sendMountSample}
                  todoList={todo}
                />
                <TodoTree
                  show={visibleList === 'todo'}
                  list={todo}
                  sampleInformation={queue}
                  queue={queue}
                  collapseSample={collapseSample}
                  displayData={displayData}
                  mount={sendMountSample}
                />
              </div>
      </div>
    );
  }
}
