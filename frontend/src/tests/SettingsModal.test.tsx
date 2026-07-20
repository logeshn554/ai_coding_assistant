import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SettingsModal from '../components/SettingsModal';

describe('SettingsModal', () => {
  const mockOnClose = vi.fn();
  const mockOnProfileChanged = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    
    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/profiles')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            active_profile_id: 'default-ollama',
            profiles: [
              {
                id: 'default-ollama',
                name: 'Ollama Local',
                api_key: '',
                base_url: 'http://localhost:11434/v1',
                model_name: '',
                api_format: 'openai'
              }
            ]
          })
        });
      }
      
      if (url.includes('/api/config/settings')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            exclude_list: ['.git', 'node_modules'],
            auto_backup_enabled: true,
            agent_model_name: '',
            agent_models: {}
          })
        });
      }

      if (url.includes('/api/permissions')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            project: [],
            session: []
          })
        });
      }

      if (url.includes('/api/models/fetch')) {
        return new Promise(resolve => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: () => Promise.resolve({
                success: true,
                models: ['model-1', 'model-2']
              })
            });
          }, 50);
        });
      }

      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      });
    });
  });

  it('renders modal and switches between tabs', async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={mockOnClose}
        onProfileChanged={mockOnProfileChanged}
      />
    );

    // Wait for async load of default profile configuration
    await screen.findByText('Edit Profile');

    const permissionsTabButton = screen.getByRole('button', { name: /Terminal Permissions/i });
    fireEvent.click(permissionsTabButton);
    expect(screen.getByText('Granted Terminal Command Permissions')).toBeInTheDocument();

    const preferencesTabButton = screen.getByRole('button', { name: /General Preferences/i });
    fireEvent.click(preferencesTabButton);
    expect(screen.getByText('Workspace Settings & Preferences')).toBeInTheDocument();
  });

  it('handles editing profile manually', async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={mockOnClose}
        onProfileChanged={mockOnProfileChanged}
      />
    );

    await screen.findByText('Ollama Local');

    const profileItem = screen.getByText('Ollama Local');
    fireEvent.click(profileItem);

    const nameInput = screen.getByPlaceholderText(/e\.g\. My Anthropic Profile/i);
    fireEvent.change(nameInput, { target: { value: 'New Custom Profile Name' } });

    expect(nameInput).toHaveValue('New Custom Profile Name');
  });

  it('handles fetching models and shows loading status', async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={mockOnClose}
        onProfileChanged={mockOnProfileChanged}
      />
    );

    await screen.findByText('Ollama Local');
    
    // Click Add Profile to create profile with no model name
    const addButton = screen.getByRole('button', { name: /Add Profile/i });
    fireEvent.click(addButton);

    // Enter API key
    const apiKeyInput = screen.getByPlaceholderText(/Paste your API key here/i);
    fireEvent.change(apiKeyInput, { target: { value: 'test-api-key' } });

    // Click "Fetch & List Models"
    const fetchButton = screen.getByRole('button', { name: /Fetch & List Models/i });
    fireEvent.click(fetchButton);

    // Verify loading status
    expect(screen.getByText(/Fetching Models.../i)).toBeInTheDocument();

    // Verify list loads
    await waitFor(() => {
      expect(screen.getByText(/Model Name/i)).toBeInTheDocument();
    });
  });

});