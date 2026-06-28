/**
 * Page Exploration Manager - Main component
 */

import React, { useState } from 'react';
import { CreateExplorationForm } from './CreateExplorationForm';
import { ExplorationProgressPanel } from './ExplorationProgressPanel';

interface PageExplorationManagerProps {
  projectId: string;
}

export const PageExplorationManager: React.FC<PageExplorationManagerProps> = ({
  projectId,
}) => {
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const handleExplorationCreated = (runId: string) => {
    setCurrentRunId(runId);
    setShowForm(false);
  };

  const handleExplorationCompleted = () => {
    // Optionally refresh page list or show results
    console.log('Exploration completed!');
  };

  const handleExplorationFailed = () => {
    console.log('Exploration failed!');
  };

  return (
    <div className="page-exploration-manager">
      <div className="manager-header">
        <h2>Page Exploration</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn-primary"
          disabled={!!currentRunId}
        >
          {showForm ? 'Cancel' : 'New Exploration'}
        </button>
      </div>

      {showForm && (
        <div className="form-container">
          <CreateExplorationForm
            projectId={projectId}
            onSuccess={handleExplorationCreated}
            onError={(error) => {
              console.error('Failed to create exploration:', error);
              alert(`Failed to create exploration: ${error.message}`);
            }}
          />
        </div>
      )}

      {currentRunId && (
        <div className="progress-container">
          <ExplorationProgressPanel
            runId={currentRunId}
            onCompleted={handleExplorationCompleted}
            onFailed={handleExplorationFailed}
          />
          <button
            onClick={() => setCurrentRunId(null)}
            className="btn-secondary"
            style={{ marginTop: '20px' }}
          >
            Close Progress View
          </button>
        </div>
      )}

      {!showForm && !currentRunId && (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <h3>No Active Exploration</h3>
          <p>Click "New Exploration" to start exploring pages</p>
        </div>
      )}
    </div>
  );
};
