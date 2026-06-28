/**
 * Create Exploration Form Component
 */

import React, { useState } from 'react';
import { explorationAPI, CreateExplorationRequest } from '../api/explorationAPI';

interface CreateExplorationFormProps {
  projectId: string;
  onSuccess?: (runId: string) => void;
  onError?: (error: Error) => void;
}

export const CreateExplorationForm: React.FC<CreateExplorationFormProps> = ({
  projectId,
  onSuccess,
  onError,
}) => {
  const [startUrl, setStartUrl] = useState('');
  const [scope, setScope] = useState('');
  const [maxDepth, setMaxDepth] = useState(3);
  const [maxPages, setMaxPages] = useState(50);
  const [maxDuration, setMaxDuration] = useState(3600);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!startUrl.trim()) {
      newErrors.startUrl = 'Start URL is required';
    } else {
      try {
        new URL(startUrl);
      } catch {
        newErrors.startUrl = 'Invalid URL format';
      }
    }

    if (scope && scope.trim()) {
      try {
        new URL(scope);
      } catch {
        newErrors.scope = 'Invalid scope URL format';
      }
    }

    if (maxDepth < 1 || maxDepth > 10) {
      newErrors.maxDepth = 'Max depth must be between 1 and 10';
    }

    if (maxPages < 1 || maxPages > 500) {
      newErrors.maxPages = 'Max pages must be between 1 and 500';
    }

    if (maxDuration < 60 || maxDuration > 7200) {
      newErrors.maxDuration = 'Max duration must be between 60 and 7200 seconds';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      const request: CreateExplorationRequest = {
        project_id: projectId,
        start_url: startUrl.trim(),
        scope: scope.trim() || undefined,
        max_depth: maxDepth,
        max_pages: maxPages,
        max_duration_seconds: maxDuration,
      };

      const result = await explorationAPI.createRun(request);
      onSuccess?.(result.run_id);

      // Reset form
      setStartUrl('');
      setScope('');
      setMaxDepth(3);
      setMaxPages(50);
      setMaxDuration(3600);
    } catch (error) {
      const err = error instanceof Error ? error : new Error('Unknown error');
      setErrors({ submit: err.message });
      onError?.(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="create-exploration-form">
      <div className="form-section">
        <h3>Exploration Configuration</h3>

        <div className="form-field">
          <label htmlFor="start-url">
            Start URL <span className="required">*</span>
          </label>
          <input
            id="start-url"
            type="text"
            value={startUrl}
            onChange={(e) => setStartUrl(e.target.value)}
            placeholder="https://app.example.com/workspace"
            disabled={isSubmitting}
          />
          {errors.startUrl && <span className="error">{errors.startUrl}</span>}
          <span className="hint">The URL where exploration should begin</span>
        </div>

        <div className="form-field">
          <label htmlFor="scope">Scope (optional)</label>
          <input
            id="scope"
            type="text"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            placeholder="https://app.example.com/workspace"
            disabled={isSubmitting}
          />
          {errors.scope && <span className="error">{errors.scope}</span>}
          <span className="hint">
            Only explore URLs within this scope. Leave empty to use start URL domain.
          </span>
        </div>
      </div>

      <div className="form-section">
        <h3>Limits</h3>

        <div className="form-row">
          <div className="form-field">
            <label htmlFor="max-depth">Max Depth</label>
            <input
              id="max-depth"
              type="number"
              min={1}
              max={10}
              value={maxDepth}
              onChange={(e) => setMaxDepth(parseInt(e.target.value) || 3)}
              disabled={isSubmitting}
            />
            {errors.maxDepth && <span className="error">{errors.maxDepth}</span>}
            <span className="hint">Maximum exploration depth (1-10)</span>
          </div>

          <div className="form-field">
            <label htmlFor="max-pages">Max Pages</label>
            <input
              id="max-pages"
              type="number"
              min={1}
              max={500}
              value={maxPages}
              onChange={(e) => setMaxPages(parseInt(e.target.value) || 50)}
              disabled={isSubmitting}
            />
            {errors.maxPages && <span className="error">{errors.maxPages}</span>}
            <span className="hint">Maximum pages to explore (1-500)</span>
          </div>

          <div className="form-field">
            <label htmlFor="max-duration">Max Duration (seconds)</label>
            <input
              id="max-duration"
              type="number"
              min={60}
              max={7200}
              value={maxDuration}
              onChange={(e) => setMaxDuration(parseInt(e.target.value) || 3600)}
              disabled={isSubmitting}
            />
            {errors.maxDuration && <span className="error">{errors.maxDuration}</span>}
            <span className="hint">Maximum duration in seconds (60-7200)</span>
          </div>
        </div>
      </div>

      {errors.submit && (
        <div className="form-error">
          <strong>Error:</strong> {errors.submit}
        </div>
      )}

      <div className="form-actions">
        <button type="submit" disabled={isSubmitting} className="btn-primary">
          {isSubmitting ? 'Creating...' : 'Start Exploration'}
        </button>
      </div>
    </form>
  );
};
