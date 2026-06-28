/**
 * Exploration Progress Panel Component
 *
 * Displays real-time exploration progress using SSE
 */

import React, { useEffect, useState } from 'react';
import { useExplorationStream, ExplorationEvent } from '../hooks/useExplorationStream';

interface ExplorationProgressPanelProps {
  runId: string;
  onCompleted?: () => void;
  onFailed?: () => void;
}

interface ProgressStats {
  pagesExplored: number;
  queueSize: number;
  progressPercentage: number;
  currentUrl: string;
  message: string;
}

export const ExplorationProgressPanel: React.FC<ExplorationProgressPanelProps> = ({
  runId,
  onCompleted,
  onFailed,
}) => {
  const [stats, setStats] = useState<ProgressStats>({
    pagesExplored: 0,
    queueSize: 0,
    progressPercentage: 0,
    currentUrl: '',
    message: 'Initializing...',
  });

  const [discoveredPages, setDiscoveredPages] = useState<string[]>([]);
  const [completedPages, setCompletedPages] = useState<string[]>([]);
  const [failedPages, setFailedPages] = useState<Array<{ page: string; error: string }>>([]);
  const [status, setStatus] = useState<'connecting' | 'running' | 'completed' | 'failed'>(
    'connecting'
  );

  const { isConnected, error, events } = useExplorationStream(runId, {
    onEvent: (event: ExplorationEvent) => {
      handleEvent(event);
    },
    onConnected: () => {
      setStatus('running');
      setStats((prev) => ({ ...prev, message: 'Connected. Waiting for updates...' }));
    },
    onCompleted: () => {
      setStatus('completed');
      onCompleted?.();
    },
    onFailed: () => {
      setStatus('failed');
      onFailed?.();
    },
  });

  const handleEvent = (event: ExplorationEvent) => {
    const { type, data } = event;

    switch (type) {
      case 'exploration.started':
        setStats({
          pagesExplored: 0,
          queueSize: 0,
          progressPercentage: 0,
          currentUrl: data.start_url,
          message: `Starting exploration from ${data.start_url}`,
        });
        break;

      case 'exploration.progress':
        setStats({
          pagesExplored: data.pages_explored,
          queueSize: data.queue_size,
          progressPercentage: data.progress_percentage,
          currentUrl: data.current_url,
          message: data.message,
        });
        break;

      case 'exploration.page_discovered':
        setDiscoveredPages((prev) => [...prev, data.normalized_path]);
        break;

      case 'exploration.page_completed':
        setCompletedPages((prev) => [...prev, data.normalized_path]);
        break;

      case 'exploration.page_failed':
        setFailedPages((prev) => [
          ...prev,
          { page: data.normalized_path, error: data.error },
        ]);
        break;

      case 'exploration.completed':
        setStats((prev) => ({
          ...prev,
          progressPercentage: 100,
          message: `Exploration completed! Explored ${data.pages_explored} pages, found ${data.elements_found} elements.`,
        }));
        break;

      case 'exploration.failed':
        setStats((prev) => ({
          ...prev,
          message: `Exploration failed: ${data.error}`,
        }));
        break;
    }
  };

  return (
    <div className="exploration-progress-panel">
      <div className="progress-header">
        <h3>Exploration Progress</h3>
        <div className={`status-badge status-${status}`}>
          {status === 'connecting' && '🔄 Connecting...'}
          {status === 'running' && '⚡ Running'}
          {status === 'completed' && '✅ Completed'}
          {status === 'failed' && '❌ Failed'}
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <strong>Connection Error:</strong> {error.message}
        </div>
      )}

      <div className="progress-stats">
        <div className="stat-item">
          <div className="stat-label">Pages Explored</div>
          <div className="stat-value">{stats.pagesExplored}</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Queue Size</div>
          <div className="stat-value">{stats.queueSize}</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Progress</div>
          <div className="stat-value">{stats.progressPercentage.toFixed(1)}%</div>
        </div>
      </div>

      <div className="progress-bar">
        <div
          className="progress-bar-fill"
          style={{ width: `${stats.progressPercentage}%` }}
        />
      </div>

      <div className="progress-message">{stats.message}</div>

      {stats.currentUrl && (
        <div className="current-url">
          <strong>Current:</strong> {stats.currentUrl}
        </div>
      )}

      <div className="progress-details">
        <div className="detail-section">
          <h4>Discovered Pages ({discoveredPages.length})</h4>
          <div className="page-list">
            {discoveredPages.slice(-5).map((page, idx) => (
              <div key={idx} className="page-item">
                📄 {page}
              </div>
            ))}
            {discoveredPages.length > 5 && (
              <div className="page-item-more">
                ...and {discoveredPages.length - 5} more
              </div>
            )}
          </div>
        </div>

        <div className="detail-section">
          <h4>Completed Pages ({completedPages.length})</h4>
          <div className="page-list">
            {completedPages.slice(-5).map((page, idx) => (
              <div key={idx} className="page-item">
                ✅ {page}
              </div>
            ))}
            {completedPages.length > 5 && (
              <div className="page-item-more">
                ...and {completedPages.length - 5} more
              </div>
            )}
          </div>
        </div>

        {failedPages.length > 0 && (
          <div className="detail-section">
            <h4>Failed Pages ({failedPages.length})</h4>
            <div className="page-list">
              {failedPages.map((item, idx) => (
                <div key={idx} className="page-item error">
                  ❌ {item.page}
                  <div className="error-detail">{item.error}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="event-log">
        <h4>Event Log</h4>
        <div className="event-list">
          {events.slice(-10).reverse().map((event, idx) => (
            <div key={idx} className="event-item">
              <span className="event-time">
                {new Date(event.timestamp).toLocaleTimeString()}
              </span>
              <span className="event-type">{event.type}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
