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
            active_profile_id: 'default-anthropic',
            profiles: [
              {
                id: 'default-anthropic',
                name: 'Anthropic Claude 3.5 Sonnet',
                api_key: '••••••••••••••••',
                base_url: 'https://api.anthropic.com/v1',
                model_name: 'claude-sonnet-4-6',
                api_format: 'anthropic'
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

  it('loads preset and updates the form values', async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={mockOnClose}
        onProfileChanged={mockOnProfileChanged}
      />
    );

    await screen.findByText('Anthropic Claude 3.5 Sonnet');

    const profileItem = screen.getByText('Anthropic Claude 3.5 Sonnet');
    fireEvent.click(profileItem);

    // Select the first combobox which is the Model Preset select
    const selectEl = screen.getAllByRole('combobox')[0];
    fireEvent.change(selectEl, { target: { value: '1' } });

    await waitFor(() => {
      const inputs = screen.getAllByRole('textbox');
      const profileNameInput = inputs.find(i => (i as HTMLInputElement).value === 'OpenAI GPT-4o');
      expect(profileNameInput).toBeDefined();
    });
  });

  it('handles fetching models and shows loading status', async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={mockOnClose}
        onProfileChanged={mockOnProfileChanged}
      />
    );

    await screen.findByText('Anthropic Claude 3.5 Sonnet');
    
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