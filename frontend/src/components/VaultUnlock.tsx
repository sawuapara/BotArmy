import { useState } from 'react';
import { Eye, EyeOff, Lock, Key, AlertCircle, Loader2, User, Mail } from 'lucide-react';
import { useVault } from '../context/VaultContext';

interface VaultUnlockProps {
  onUnlocked?: () => void;
}

export function VaultUnlock({ onUnlocked }: VaultUnlockProps) {
  const { isSetup, isLoading, error, setup, unlock, clearError } = useVault();

  // User fields (setup only)
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');

  // Password fields
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const isSettingUp = isSetup === false;

  // Validation
  const passwordsMatch = password === confirmPassword;
  const passwordLongEnough = password.length >= 8;
  const emailValid = email.includes('@') && email.includes('.');
  const hasRequiredFields = firstName.trim() && lastName.trim() && emailValid;

  const canSubmit = isSettingUp
    ? (passwordsMatch && passwordLongEnough && hasRequiredFields)
    : password.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    if (isSettingUp) {
      // Validate
      if (!hasRequiredFields) {
        setLocalError('Please fill in all required fields');
        return;
      }
      if (password !== confirmPassword) {
        setLocalError('Passwords do not match');
        return;
      }
      if (password.length < 8) {
        setLocalError('Password must be at least 8 characters');
        return;
      }

      const success = await setup({
        email,
        firstName,
        lastName,
        password,
      });
      if (success) {
        setPassword('');
        setConfirmPassword('');
        onUnlocked?.();
      }
    } else {
      const success = await unlock(password);
      if (success) {
        setPassword('');
        onUnlocked?.();
      }
    }
  };

  const displayError = localError || error;

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-600/20 mb-4">
              <Lock className="w-8 h-8 text-blue-400" />
            </div>
            <h1 className="text-2xl font-bold text-gray-100">
              {isSettingUp ? 'Set Up Vault' : 'Unlock Vault'}
            </h1>
            <p className="text-gray-400 mt-2">
              {isSettingUp
                ? 'Create your identity and master password to secure your vault.'
                : 'Enter your master password to access your encrypted vault.'}
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* User identity fields (setup only) */}
            {isSettingUp && (
              <>
                {/* Name fields */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label
                      htmlFor="firstName"
                      className="block text-sm font-medium text-gray-300 mb-1"
                    >
                      First Name
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <User className="w-4 h-4 text-gray-500" />
                      </div>
                      <input
                        id="firstName"
                        type="text"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        className="block w-full pl-9 pr-3 py-2.5 bg-gray-900 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="First"
                        required
                        autoFocus
                      />
                    </div>
                  </div>
                  <div>
                    <label
                      htmlFor="lastName"
                      className="block text-sm font-medium text-gray-300 mb-1"
                    >
                      Last Name
                    </label>
                    <input
                      id="lastName"
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      className="block w-full px-3 py-2.5 bg-gray-900 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="Last"
                      required
                    />
                  </div>
                </div>

                {/* Email field */}
                <div>
                  <label
                    htmlFor="email"
                    className="block text-sm font-medium text-gray-300 mb-1"
                  >
                    Email
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Mail className="w-4 h-4 text-gray-500" />
                    </div>
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="block w-full pl-9 pr-3 py-2.5 bg-gray-900 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="you@example.com"
                      required
                    />
                  </div>
                </div>

                <hr className="border-gray-700 my-4" />
              </>
            )}

            {/* Password field */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                {isSettingUp ? 'Master Password' : 'Password'}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Key className="w-4 h-4 text-gray-500" />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full pl-9 pr-10 py-2.5 bg-gray-900 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder={isSettingUp ? 'Min 8 characters' : 'Enter password'}
                  autoFocus={!isSettingUp}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4 text-gray-500 hover:text-gray-400" />
                  ) : (
                    <Eye className="w-4 h-4 text-gray-500 hover:text-gray-400" />
                  )}
                </button>
              </div>
            </div>

            {/* Confirm password field (setup only) */}
            {isSettingUp && (
              <div>
                <label
                  htmlFor="confirmPassword"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Confirm Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Key className="w-4 h-4 text-gray-500" />
                  </div>
                  <input
                    id="confirmPassword"
                    type={showPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="block w-full pl-9 pr-3 py-2.5 bg-gray-900 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Confirm password"
                    required
                  />
                </div>
              </div>
            )}

            {/* Validation hints for setup */}
            {isSettingUp && password.length > 0 && (
              <div className="space-y-1 text-sm">
                {!passwordLongEnough && (
                  <div className="flex items-center gap-2 text-yellow-400">
                    <AlertCircle className="w-4 h-4" />
                    <span>Password must be at least 8 characters</span>
                  </div>
                )}
                {confirmPassword.length > 0 && !passwordsMatch && (
                  <div className="flex items-center gap-2 text-yellow-400">
                    <AlertCircle className="w-4 h-4" />
                    <span>Passwords do not match</span>
                  </div>
                )}
              </div>
            )}

            {/* Error message */}
            {displayError && (
              <div className="flex items-center gap-2 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{displayError}</span>
              </div>
            )}

            {/* Submit button */}
            <button
              type="submit"
              disabled={isLoading || !canSubmit}
              className="w-full flex items-center justify-center gap-2 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 disabled:cursor-not-allowed rounded-lg text-white font-medium transition-colors"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  {isSettingUp ? 'Setting up...' : 'Unlocking...'}
                </>
              ) : (
                <>
                  <Lock className="w-5 h-5" />
                  {isSettingUp ? 'Create Vault' : 'Unlock'}
                </>
              )}
            </button>
          </form>

          {/* Security note */}
          <div className="mt-6 p-4 bg-gray-900 rounded-lg border border-gray-700">
            <h3 className="text-sm font-medium text-gray-300 mb-2">
              Security Information
            </h3>
            <ul className="text-xs text-gray-400 space-y-1">
              <li>
                Your password never leaves your browser after {isSettingUp ? 'setup' : 'unlock'}
              </li>
              <li>All secrets are encrypted client-side with AES-256-GCM</li>
              <li>The server only stores encrypted data it cannot read</li>
              <li>Closing the browser tab will lock the vault</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
