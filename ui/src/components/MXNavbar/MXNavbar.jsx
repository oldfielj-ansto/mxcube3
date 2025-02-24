import React from 'react';
import { Container, Navbar, Nav, Button } from 'react-bootstrap';
import { LinkContainer } from 'react-router-bootstrap';
import withRouter from '../WithRouter';
import './MXNavbar.css';
import { serverIO } from '../../serverIO';

class MXNavbar extends React.Component {
  constructor(props) {
    super(props);
    this.findProposal = this.findProposal.bind(this);
    this.handleSignOutClick = this.handleSignOutClick.bind(this);
  }

  findProposal(prop) {
    return (
      `${prop.Proposal.code}${prop.Proposal.number}` ===
      this.props.selectedProposal
    );
  }

  handleSignOutClick() {
    this.props.signOut();
    serverIO.disconnect();
    this.props.router.navigate('/');
  }

  render() {
    const raStyle = this.props.user.inControl ? { color: 'white' } : {};
    const numObservers = this.props.remoteAccess.observers.length;

    document.title = `MxCuBE-Web Proposal: ${this.props.selectedProposal}`;

    const username =
      this.props.loginType === 'User'
        ? `(${this.props.user.username})`
        : `(${this.props.selectedProposal})`;

    return (
      <Navbar
        className="pt-1 pb-1 nav-container"
        bg="dark"
        variant="dark"
        collapseOnSelect
        expand="lg"
      >
        <Container fluid>
          <LinkContainer to="/remoteaccess">
            <Navbar.Brand>
              MXCuBE-Web{' '}
              <span className="brand-subtitle">({this.props.mode})</span>
            </Navbar.Brand>
          </LinkContainer>
          <Navbar.Toggle aria-controls="responsive-navbar-nav" />
          <Navbar.Collapse id="responsive-navbar-nav">
            <Nav className="m-auto">
              <LinkContainer className="me-4" to="/samplegrid">
                <Nav.Item className="nav-link">Samples</Nav.Item>
              </LinkContainer>
              <LinkContainer className="me-4" to="/datacollection">
                <Nav.Item className="nav-link">Data collection</Nav.Item>
              </LinkContainer>
              <LinkContainer className="me-4" to="/equipment">
                <Nav.Item className="nav-link">Equipment</Nav.Item>
              </LinkContainer>
              <LinkContainer to="/logging">
                <Nav.Item className="nav-link">System log</Nav.Item>
              </LinkContainer>
            </Nav>
            <Nav>
              <LinkContainer className="me-2" to="/help">
                <Nav.Item className="nav-link">
                  <span className="me-1 fas fa-lg fa-question-circle" />
                  Help
                </Nav.Item>
              </LinkContainer>
              <LinkContainer className="me-2" to="/remoteaccess">
                <Nav.Item className="nav-link">
                  <span style={raStyle} className="me-1 fas fa-lg fa-globe">
                    {numObservers > 0 ? (
                      <span className="badge-num">{numObservers}</span>
                    ) : null}
                  </span>
                  Remote
                </Nav.Item>
              </LinkContainer>
              {this.props.loginType === 'User' && (
                <Button
                  as={Nav.Link}
                  className="nav-link pe-0"
                  variant="Light"
                  onClick={this.props.handleShowProposalForm}
                >
                  <span className="me-1 fas fa-lg fa-bars" />
                  Select proposal {`(${this.props.selectedProposal})`}
                </Button>
              )}
              <Button
                as={Nav.Link}
                className="nav-link pe-0"
                variant="Light"
                onClick={this.handleSignOutClick}
              >
                <span className="me-1 fas fa-lg fa-sign-out-alt" />
                Sign out {username}
              </Button>
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>
    );
  }
}

export default withRouter(MXNavbar);
