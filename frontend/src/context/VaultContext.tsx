import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react';
import { deriveKey, encryptObject, decryptObject } from '../lib/crypto';

const API_BASE = 'http://localhost:8000';

// Session storage key for unlock status (cleared on tab close)
const VAULT_UNLOCKED_KEY = 'vault_unlocked';

interface SetupParams {
  email: string;
  firstName: string;
  lastName: string;
  password: string;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

interface VaultContextType {
  /** Whether the vault is currently unlocked (key in memory) */
  isUnlocked: boolean;
  /** Whether the vault has been set up (master password configured) */
  isSetup: boolean | null;
  /** Loading state for async operations */
  isLoading: boolean;
  /** Error message from last operation */
  error: string | null;
  /** Set up the vault with user info and master password (first time only) */
  setup: (params: SetupParams) => Promise<boolean>;
  /** Unlock the vault with the master password */
  unlock: (password: string) => Promise<boolean>;
  /** Lock the vault (clear the key from memory) */
  lock: () => void;
  /** Encrypt data for storage */
  encrypt: (data: unknown) => Promise<{ encrypted: string; iv: string }>;
  /** Decrypt stored data */
  decrypt: <T = unknown>(encrypted: string, iv: string) => Promise<T>;
  /** Clear any error */
  clearError: () => void;
  /** Refresh vault status from server */
  refreshStatus: () => Promise<void>;
}

const VaultContext = createContext<VaultContextType | null>(null);

interface VaultProviderProps {
  children: ReactNode;
}

export function VaultProvider({ children }: VaultProviderProps) {
  const [isSetup, setIsSetup] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cryptoKey, setCryptoKey] = useState<CryptoKey | null>(null);

  const isUnlocked = cryptoKey !== null;

  // Check vault status on mount
  const refreshStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/vault/status`);
      if (!res.ok) throw new Error('Failed to check vault status');
      const data = await res.json();
      setIsSetup(data.is_setup);
    } catch (e) {
      console.error('Failed to check vault status:', e);
      setError(e instanceof Error ? e.message : 'Failed to check vault status');
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // Check if we were unlocked before (session storage persists across page refreshes)
  useEffect(() => {
    const wasUnlocked = sessionStorage.getItem(VAULT_UNLOCKED_KEY);
    if (wasUnlocked && !cryptoKey) {
      // Key was lost (page refresh) - need to unlock again
      sessionStorage.removeItem(VAULT_UNLOCKED_KEY);
    }
  }, [cryptoKey]);

  const setup = useCallback(async (params: SetupParams): Promise<boolean> => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/vault/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: params.email,
          first_name: params.firstName,
          last_name: params.lastName,
          password: params.password,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to set up vault');
      }

      const data = await res.json();

      // Derive encryption key from password + salt
      const key = await deriveKey(params.password, data.salt);
      setCryptoKey(key);
      setIsSetup(true);
      sessionStorage.setItem(VAULT_UNLOCKED_KEY, 'true');

      return true;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Setup failed';
      setError(message);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const unlock = useCallback(async (password: string): Promise<boolean> => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/vault/unlock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Invalid password');
      }

      const data = await res.json();

      // Derive encryption key from password + salt
      const key = await deriveKey(password, data.salt);
      setCryptoKey(key);
      sessionStorage.setItem(VAULT_UNLOCKED_KEY, 'true');

      return true;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Unlock failed';
      setError(message);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const lock = useCallback(() => {
    setCryptoKey(null);
    sessionStorage.removeItem(VAULT_UNLOCKED_KEY);
  }, []);

  const encrypt = useCallback(
    async (data: unknown): Promise<{ encrypted: string; iv: string }> => {
      if (!cryptoKey) {
        throw new Error('Vault is locked. Unlock first.');
      }
      return encryptObject(cryptoKey, data);
    },
    [cryptoKey]
  );

  const decrypt = useCallback(
    async <T = unknown>(encrypted: string, iv: string): Promise<T> => {
      if (!cryptoKey) {
        throw new Error('Vault is locked. Unlock first.');
      }
      return decryptObject<T>(cryptoKey, encrypted, iv);
    },
    [cryptoKey]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value: VaultContextType = {
    isUnlocked,
    isSetup,
    isLoading,
    error,
    setup,
    unlock,
    lock,
    encrypt,
    decrypt,
    clearError,
    refreshStatus,
  };

  return (
    <VaultContext.Provider value={value}>{children}</VaultContext.Provider>
  );
}

export function useVault(): VaultContextType {
  const context = useContext(VaultContext);
  if (!context) {
    throw new Error('useVault must be used within a VaultProvider');
  }
  return context;
}
