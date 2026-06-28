/**
 * Example App integration
 */

import React from 'react';
import { PageExplorationManager } from './components/PageExplorationManager';
import './styles/exploration.css';

function App() {
  // In a real app, this would come from routing or context
  const projectId = 'proj-123';

  return (
    <div className="app">
      <PageExplorationManager projectId={projectId} />
    </div>
  );
}

export default App;
