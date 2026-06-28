/**
 * Custom hook for consuming SSE events from exploration API
 */

import { useEffect, useState, useCallback, useRef } from 'react';

export interface ExplorationEvent {
  type: string;
  timestamp: string;
  data: any;
}

export interface UseExplorationStreamOptions {
  onEvent?: (event: ExplorationEvent) => void;
  onError?: (error: Error) => void;
  onConnected?: () => void;
  onCompleted?: () => void;
  onFailed?: () => void;
}

export interface UseExplorationStreamResult {
  events: ExplorationEvent[];
  latestEvent: ExplorationEvent | null;
  isConnected: boolean;
  error: Error | null;
  reconnect: () => void;
  disconnect: () => void;
}

export function useExplorationStream(
  runId: string | null,
  options: UseExplorationStreamOptions = {}
): UseExplorationStreamResult {
  const [events, setEvents] = useState<ExplorationEvent[]>([]);
  const [latestEvent, setLatestEvent] = useState<ExplorationEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!runId) return;

    disconnect();

    const eventSource = new EventSource(
      `/api/exploration/runs/${runId}/events`
    );

    eventSourceRef.current = eventSource;

    eventSource.addEventListener('connected', () => {
      setIsConnected(true);
      setError(null);
      options.onConnected?.();
    });

    // Listen for all exploration event types
    const eventTypes = [
      'exploration.started',
      'exploration.progress',
      'exploration.page_discovered',
      'exploration.page_completed',
      'exploration.page_failed',
      'exploration.error',
      'exploration.completed',
      'exploration.failed',
    ];

    eventTypes.forEach((eventType) => {
      eventSource.addEventListener(eventType, (e: MessageEvent) => {
        try {
          const event: ExplorationEvent = JSON.parse(e.data);

          setEvents((prev) => [...prev, event]);
          setLatestEvent(event);
          options.onEvent?.(event);

          // Handle terminal events
          if (eventType === 'exploration.completed') {
            options.onCompleted?.();
            disconnect();
          } else if (eventType === 'exploration.failed') {
            options.onFailed?.();
            disconnect();
          }
        } catch (err) {
          console.error('Failed to parse event:', err);
        }
      });
    });

    eventSource.onerror = (err) => {
      console.error('SSE error:', err);
      const error = new Error('Connection to server lost');
      setError(error);
      setIsConnected(false);
      options.onError?.(error);

      // Auto-reconnect after 5 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('Attempting to reconnect...');
        connect();
      }, 5000);
    };
  }, [runId, disconnect, options]);

  useEffect(() => {
    if (runId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [runId, connect, disconnect]);

  return {
    events,
    latestEvent,
    isConnected,
    error,
    reconnect: connect,
    disconnect,
  };
}
