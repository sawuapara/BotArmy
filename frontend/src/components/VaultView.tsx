import { useState, useEffect, useCallback } from 'react';
import {
  Lock,
  FolderPlus,
  FilePlus,
  Folder,
  FolderOpen,
  Key,
  FileText,
  Shield,
  Eye,
  EyeOff,
  Trash2,
  Edit2,
  Copy,
  Check,
  X,
  ChevronRight,
  ChevronDown,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useVault } from '../context/VaultContext';
import { useNamespace } from '../context/NamespaceContext';
import { VaultUnlock } from './VaultUnlock';
import { AppHeader } from './AppHeader';
import { API_BASE } from '../lib/config';

interface VaultFolder {
  id: string;
  namespace_id: string;
  parent_folder_id: string | null;
  name: string;
  description: string | null;
}

interface VaultItem {
  id: string;
  namespace_id: string;
  folder_id: string | null;
  name: string;
  item_type: string;
  encrypted_data?: string;
  iv?: string;
  description: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  expires_at: string | null;
}

interface DecryptedContent {
  value?: string;
  username?: string;
  password?: string;
  notes?: string;
  [key: string]: unknown;
}

// Item type icons
const itemTypeIcons: Record<string, typeof Key> = {
  secret: Key,
  credential: Shield,
  api_key: Key,
  certificate: FileText,
  note: FileText,
};

export function VaultView() {
  const { isUnlocked, lock, encrypt, decrypt } = useVault();
  const { selectedNamespace } = useNamespace();

  const [currentUser, setCurrentUser] = useState<{ email: string; first_name: string; last_name: string } | null>(null);
  const [folders, setFolders] = useState<VaultFolder[]>([]);
  const [items, setItems] = useState<VaultItem[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<VaultItem | null>(null);
  const [decryptedContent, setDecryptedContent] = useState<DecryptedContent | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [showNewFolderModal, setShowNewFolderModal] = useState(false);
  const [showNewItemModal, setShowNewItemModal] = useState(false);
  const [showEditItemModal, setShowEditItemModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<{ type: 'folder' | 'item'; id: string } | null>(null);

  // Reveal states
  const [revealedFields, setRevealedFields] = useState<Set<string>>(new Set());
  const [copiedField, setCopiedField] = useState<string | null>(null);

  // Fetch current user
  useEffect(() => {
    const fetchCurrentUser = async () => {
      try {
        const res = await fetch(`${API_BASE}/vault/me`);
        if (res.ok) {
          const data = await res.json();
          setCurrentUser(data);
        }
      } catch (e) {
        console.error('Failed to fetch current user:', e);
      }
    };

    fetchCurrentUser();
  }, []);

  // Fetch folders when namespace changes
  useEffect(() => {
    const fetchFolders = async () => {
      try {
        const url = selectedNamespace === 'All'
          ? `${API_BASE}/vault/folders`
          : `${API_BASE}/vault/folders?namespace_id=${selectedNamespace}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch folders');
        const data = await res.json();
        setFolders(data);
      } catch (e) {
        console.error('Failed to fetch folders:', e);
      }
    };
    fetchFolders();
  }, [selectedNamespace]);

  // Fetch items when namespace or folder changes
  useEffect(() => {
    const fetchItems = async () => {
      try {
        let url = `${API_BASE}/vault/items`;
        const params = new URLSearchParams();

        if (selectedNamespace !== 'All') {
          params.append('namespace_id', selectedNamespace);
        }
        if (selectedFolder) {
          params.append('folder_id', selectedFolder);
        }

        if (params.toString()) {
          url += `?${params.toString()}`;
        }

        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch items');
        const data = await res.json();
        setItems(data);
      } catch (e) {
        console.error('Failed to fetch items:', e);
      }
    };
    fetchItems();
  }, [selectedNamespace, selectedFolder]);

  // Decrypt item when selected
  const handleSelectItem = useCallback(
    async (item: VaultItem) => {
      setSelectedItem(item);
      setDecryptedContent(null);
      setRevealedFields(new Set());

      if (!isUnlocked) return;

      try {
        // Fetch full item with encrypted data
        const res = await fetch(`${API_BASE}/vault/items/${item.id}`);
        if (!res.ok) throw new Error('Failed to fetch item');
        const fullItem = await res.json();

        if (fullItem.encrypted_data && fullItem.iv) {
          const decrypted = await decrypt<DecryptedContent>(
            fullItem.encrypted_data,
            fullItem.iv
          );
          setDecryptedContent(decrypted);
        }
      } catch (e) {
        console.error('Failed to decrypt item:', e);
        setError('Failed to decrypt item. Wrong password?');
      }
    },
    [isUnlocked, decrypt]
  );

  // Toggle folder expansion
  const toggleFolder = (folderId: string) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(folderId)) {
      newExpanded.delete(folderId);
    } else {
      newExpanded.add(folderId);
    }
    setExpandedFolders(newExpanded);
  };

  // Copy to clipboard
  const copyToClipboard = async (text: string, fieldName: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(fieldName);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  };

  // Toggle field reveal
  const toggleReveal = (fieldName: string) => {
    const newRevealed = new Set(revealedFields);
    if (newRevealed.has(fieldName)) {
      newRevealed.delete(fieldName);
    } else {
      newRevealed.add(fieldName);
    }
    setRevealedFields(newRevealed);
  };

  // Build folder tree
  const buildFolderTree = (parentId: string | null = null): VaultFolder[] => {
    return folders.filter((f) => f.parent_folder_id === parentId);
  };

  // Refresh data
  const refreshData = useCallback(async () => {
    if (!selectedNamespace) return;
    try {
      const [foldersRes, itemsRes] = await Promise.all([
        fetch(`${API_BASE}/vault/folders?namespace_id=${selectedNamespace}`),
        fetch(
          `${API_BASE}/vault/items?namespace_id=${selectedNamespace}${
            selectedFolder ? `&folder_id=${selectedFolder}` : '&folder_id=null'
          }`
        ),
      ]);
      if (foldersRes.ok) setFolders(await foldersRes.json());
      if (itemsRes.ok) setItems(await itemsRes.json());
    } catch (e) {
      console.error('Failed to refresh:', e);
    }
  }, [selectedNamespace, selectedFolder]);

  // If vault not unlocked, show unlock screen
  if (!isUnlocked) {
    return <VaultUnlock />;
  }

  // Reset folder/item selection when namespace changes
  useEffect(() => {
    setSelectedFolder(null);
    setSelectedItem(null);
  }, [selectedNamespace]);

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <AppHeader
        isVault
        onLockVault={lock}
        currentUser={currentUser}
      />

      {/* Main content */}
      <main className="p-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left: Folder tree */}
          <div className="col-span-3">
            <div className="bg-gray-800 rounded-lg border border-gray-700">
              <div className="p-4 border-b border-gray-700 flex items-center justify-between">
                <h2 className="font-medium text-gray-200">Folders</h2>
                <button
                  onClick={() => setShowNewFolderModal(true)}
                  className="p-1.5 hover:bg-gray-700 rounded"
                  title="New Folder"
                >
                  <FolderPlus className="w-4 h-4 text-gray-400" />
                </button>
              </div>
              <div className="p-2">
                {/* Root level items */}
                <button
                  onClick={() => {
                    setSelectedFolder(null);
                    setSelectedItem(null);
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded text-left ${
                    selectedFolder === null
                      ? 'bg-blue-600/20 text-blue-400'
                      : 'text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  <Folder className="w-4 h-4" />
                  <span>All Items</span>
                </button>

                {/* Folder tree */}
                <FolderTree
                  folders={folders}
                  parentId={null}
                  selectedFolder={selectedFolder}
                  expandedFolders={expandedFolders}
                  onSelect={(id) => {
                    setSelectedFolder(id);
                    setSelectedItem(null);
                  }}
                  onToggle={toggleFolder}
                  onDelete={(id) => setShowDeleteConfirm({ type: 'folder', id })}
                />
              </div>
            </div>
          </div>

          {/* Middle: Item list */}
          <div className="col-span-4">
            <div className="bg-gray-800 rounded-lg border border-gray-700">
              <div className="p-4 border-b border-gray-700 flex items-center justify-between">
                <h2 className="font-medium text-gray-200">
                  Items {items.length > 0 && `(${items.length})`}
                </h2>
                <button
                  onClick={() => setShowNewItemModal(true)}
                  className="p-1.5 hover:bg-gray-700 rounded"
                  title="New Item"
                >
                  <FilePlus className="w-4 h-4 text-gray-400" />
                </button>
              </div>
              <div className="divide-y divide-gray-700 max-h-[calc(100vh-280px)] overflow-y-auto">
                {items.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <Key className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No items in this location</p>
                    <button
                      onClick={() => setShowNewItemModal(true)}
                      className="mt-3 text-blue-400 hover:text-blue-300"
                    >
                      Add your first secret
                    </button>
                  </div>
                ) : (
                  items.map((item) => {
                    const Icon = itemTypeIcons[item.item_type] || Key;
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleSelectItem(item)}
                        className={`w-full flex items-center gap-3 p-4 text-left hover:bg-gray-700/50 ${
                          selectedItem?.id === item.id ? 'bg-gray-700' : ''
                        }`}
                      >
                        <Icon className="w-5 h-5 text-gray-400" />
                        <div className="flex-1 min-w-0">
                          <div className="text-gray-200 font-medium truncate">
                            {item.name}
                          </div>
                          <div className="text-xs text-gray-500 flex items-center gap-2">
                            <span className="capitalize">{item.item_type}</span>
                            {item.expires_at && (
                              <span className="text-yellow-500">Expires</span>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* Right: Item details */}
          <div className="col-span-5">
            {selectedItem ? (
              <div className="bg-gray-800 rounded-lg border border-gray-700">
                <div className="p-4 border-b border-gray-700 flex items-center justify-between">
                  <h2 className="font-medium text-gray-200">{selectedItem.name}</h2>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowEditItemModal(true)}
                      className="p-1.5 hover:bg-gray-700 rounded"
                      title="Edit"
                    >
                      <Edit2 className="w-4 h-4 text-gray-400" />
                    </button>
                    <button
                      onClick={() =>
                        setShowDeleteConfirm({ type: 'item', id: selectedItem.id })
                      }
                      className="p-1.5 hover:bg-gray-700 rounded"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4 text-red-400" />
                    </button>
                  </div>
                </div>
                <div className="p-4 space-y-4">
                  {/* Type badge */}
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300 capitalize">
                      {selectedItem.item_type}
                    </span>
                    {selectedItem.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>

                  {/* Description */}
                  {selectedItem.description && (
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">
                        Description
                      </label>
                      <p className="text-gray-300">{selectedItem.description}</p>
                    </div>
                  )}

                  {/* Decrypted content */}
                  {decryptedContent ? (
                    <div className="space-y-3">
                      {/* Value field */}
                      {decryptedContent.value && (
                        <SecretField
                          label="Value"
                          value={decryptedContent.value}
                          revealed={revealedFields.has('value')}
                          copied={copiedField === 'value'}
                          onToggleReveal={() => toggleReveal('value')}
                          onCopy={() =>
                            copyToClipboard(decryptedContent.value!, 'value')
                          }
                        />
                      )}

                      {/* Username field */}
                      {decryptedContent.username && (
                        <SecretField
                          label="Username"
                          value={decryptedContent.username}
                          revealed={true}
                          copied={copiedField === 'username'}
                          onCopy={() =>
                            copyToClipboard(decryptedContent.username!, 'username')
                          }
                        />
                      )}

                      {/* Password field */}
                      {decryptedContent.password && (
                        <SecretField
                          label="Password"
                          value={decryptedContent.password}
                          revealed={revealedFields.has('password')}
                          copied={copiedField === 'password'}
                          onToggleReveal={() => toggleReveal('password')}
                          onCopy={() =>
                            copyToClipboard(decryptedContent.password!, 'password')
                          }
                        />
                      )}

                      {/* Notes field */}
                      {decryptedContent.notes && (
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">
                            Notes
                          </label>
                          <p className="text-gray-300 whitespace-pre-wrap">
                            {decryptedContent.notes}
                          </p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center justify-center py-8 text-gray-500">
                      <Loader2 className="w-5 h-5 animate-spin mr-2" />
                      Decrypting...
                    </div>
                  )}

                  {/* Metadata */}
                  <div className="pt-4 border-t border-gray-700">
                    <div className="grid grid-cols-2 gap-4 text-xs">
                      <div>
                        <span className="text-gray-500">Created</span>
                        <p className="text-gray-400">
                          {new Date(selectedItem.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-500">Updated</span>
                        <p className="text-gray-400">
                          {new Date(selectedItem.updated_at).toLocaleString()}
                        </p>
                      </div>
                      {selectedItem.expires_at && (
                        <div>
                          <span className="text-gray-500">Expires</span>
                          <p className="text-yellow-400">
                            {new Date(selectedItem.expires_at).toLocaleString()}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center text-gray-500">
                <Lock className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Select an item to view details</p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Modals */}
      {showNewFolderModal && (
        <NewFolderModal
          namespaceId={selectedNamespace!}
          parentFolderId={selectedFolder}
          onClose={() => setShowNewFolderModal(false)}
          onCreated={refreshData}
        />
      )}

      {showNewItemModal && (
        <NewItemModal
          namespaceId={selectedNamespace!}
          folderId={selectedFolder}
          encrypt={encrypt}
          onClose={() => setShowNewItemModal(false)}
          onCreated={refreshData}
        />
      )}

      {showEditItemModal && selectedItem && decryptedContent && (
        <EditItemModal
          item={selectedItem}
          decryptedContent={decryptedContent}
          encrypt={encrypt}
          onClose={() => setShowEditItemModal(false)}
          onUpdated={() => {
            refreshData();
            handleSelectItem(selectedItem);
          }}
        />
      )}

      {showDeleteConfirm && (
        <DeleteConfirmModal
          type={showDeleteConfirm.type}
          id={showDeleteConfirm.id}
          onClose={() => setShowDeleteConfirm(null)}
          onDeleted={() => {
            refreshData();
            if (showDeleteConfirm.type === 'item') {
              setSelectedItem(null);
              setDecryptedContent(null);
            }
          }}
        />
      )}

      {/* Error toast */}
      {error && (
        <div className="fixed bottom-4 right-4 flex items-center gap-2 p-4 bg-red-900/90 border border-red-700 rounded-lg text-red-200">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-2">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}

// Folder tree component
function FolderTree({
  folders,
  parentId,
  selectedFolder,
  expandedFolders,
  onSelect,
  onToggle,
  onDelete,
  depth = 0,
}: {
  folders: VaultFolder[];
  parentId: string | null;
  selectedFolder: string | null;
  expandedFolders: Set<string>;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
  depth?: number;
}) {
  const childFolders = folders.filter((f) => f.parent_folder_id === parentId);

  if (childFolders.length === 0) return null;

  return (
    <div className={depth > 0 ? 'ml-4' : ''}>
      {childFolders.map((folder) => {
        const hasChildren = folders.some((f) => f.parent_folder_id === folder.id);
        const isExpanded = expandedFolders.has(folder.id);
        const isSelected = selectedFolder === folder.id;

        return (
          <div key={folder.id}>
            <div
              className={`flex items-center gap-1 px-2 py-1.5 rounded group ${
                isSelected
                  ? 'bg-blue-600/20 text-blue-400'
                  : 'text-gray-300 hover:bg-gray-700'
              }`}
            >
              {hasChildren ? (
                <button
                  onClick={() => onToggle(folder.id)}
                  className="p-0.5"
                >
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                </button>
              ) : (
                <span className="w-5" />
              )}
              <button
                onClick={() => onSelect(folder.id)}
                className="flex items-center gap-2 flex-1 text-left"
              >
                {isExpanded ? (
                  <FolderOpen className="w-4 h-4" />
                ) : (
                  <Folder className="w-4 h-4" />
                )}
                <span className="truncate">{folder.name}</span>
              </button>
              <button
                onClick={() => onDelete(folder.id)}
                className="p-1 opacity-0 group-hover:opacity-100 hover:text-red-400"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
            {isExpanded && (
              <FolderTree
                folders={folders}
                parentId={folder.id}
                selectedFolder={selectedFolder}
                expandedFolders={expandedFolders}
                onSelect={onSelect}
                onToggle={onToggle}
                onDelete={onDelete}
                depth={depth + 1}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Secret field component
function SecretField({
  label,
  value,
  revealed,
  copied,
  onToggleReveal,
  onCopy,
}: {
  label: string;
  value: string;
  revealed: boolean;
  copied: boolean;
  onToggleReveal?: () => void;
  onCopy: () => void;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <div className="flex items-center gap-2 bg-gray-900 rounded-lg px-3 py-2">
        <code className="flex-1 text-gray-200 font-mono text-sm overflow-x-auto">
          {revealed ? value : '\u2022'.repeat(Math.min(value.length, 24))}
        </code>
        {onToggleReveal && (
          <button
            onClick={onToggleReveal}
            className="p-1 hover:bg-gray-700 rounded"
            title={revealed ? 'Hide' : 'Reveal'}
          >
            {revealed ? (
              <EyeOff className="w-4 h-4 text-gray-400" />
            ) : (
              <Eye className="w-4 h-4 text-gray-400" />
            )}
          </button>
        )}
        <button
          onClick={onCopy}
          className="p-1 hover:bg-gray-700 rounded"
          title="Copy"
        >
          {copied ? (
            <Check className="w-4 h-4 text-green-400" />
          ) : (
            <Copy className="w-4 h-4 text-gray-400" />
          )}
        </button>
      </div>
    </div>
  );
}

// New Folder Modal
function NewFolderModal({
  namespaceId,
  parentFolderId,
  onClose,
  onCreated,
}: {
  namespaceId: string;
  parentFolderId: string | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/vault/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          namespace_id: namespaceId,
          parent_folder_id: parentFolderId,
          name,
          description: description || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create folder');
      }

      onCreated();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create folder');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal title="New Folder" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
            placeholder="Folder name"
            required
            autoFocus
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Description (optional)
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
            placeholder="What's in this folder?"
          />
        </div>
        {error && (
          <div className="text-red-400 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-gray-200"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white disabled:opacity-50"
          >
            {isLoading ? 'Creating...' : 'Create Folder'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// New Item Modal
function NewItemModal({
  namespaceId,
  folderId,
  encrypt,
  onClose,
  onCreated,
}: {
  namespaceId: string;
  folderId: string | null;
  encrypt: (data: unknown) => Promise<{ encrypted: string; iv: string }>;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState('');
  const [itemType, setItemType] = useState('secret');
  const [description, setDescription] = useState('');
  const [value, setValue] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [notes, setNotes] = useState('');
  const [tags, setTags] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      // Build content object based on type
      const content: DecryptedContent = {};
      if (itemType === 'credential') {
        content.username = username;
        content.password = password;
      } else {
        content.value = value;
      }
      if (notes) content.notes = notes;

      // Encrypt content
      const { encrypted, iv } = await encrypt(content);

      const res = await fetch(`${API_BASE}/vault/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          namespace_id: namespaceId,
          folder_id: folderId,
          name,
          item_type: itemType,
          description: description || null,
          encrypted_data: encrypted,
          iv,
          tags: tags ? tags.split(',').map((t) => t.trim()) : [],
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create item');
      }

      onCreated();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create item');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal title="New Secret" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
              placeholder="e.g., OpenAI API Key"
              required
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Type
            </label>
            <select
              value={itemType}
              onChange={(e) => setItemType(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
            >
              <option value="secret">Secret</option>
              <option value="credential">Credential</option>
              <option value="api_key">API Key</option>
              <option value="certificate">Certificate</option>
              <option value="note">Note</option>
            </select>
          </div>
        </div>

        {itemType === 'credential' ? (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
                placeholder="Username or email"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
                placeholder="Password"
              />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Value
            </label>
            <textarea
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200 font-mono text-sm"
              placeholder="Your secret value"
              rows={3}
              required
            />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Notes (optional)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
            placeholder="Additional notes..."
            rows={2}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Description (optional)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
              placeholder="What's this for?"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Tags (comma-separated)
            </label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
              placeholder="e.g., production, aws"
            />
          </div>
        </div>

        {error && (
          <div className="text-red-400 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-gray-200"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white disabled:opacity-50"
          >
            {isLoading ? 'Encrypting...' : 'Save Secret'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// Edit Item Modal
function EditItemModal({
  item,
  decryptedContent,
  encrypt,
  onClose,
  onUpdated,
}: {
  item: VaultItem;
  decryptedContent: DecryptedContent;
  encrypt: (data: unknown) => Promise<{ encrypted: string; iv: string }>;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [name, setName] = useState(item.name);
  const [itemType, setItemType] = useState(item.item_type);
  const [description, setDescription] = useState(item.description || '');
  const [value, setValue] = useState(decryptedContent.value || '');
  const [username, setUsername] = useState(decryptedContent.username || '');
  const [password, setPassword] = useState(decryptedContent.password || '');
  const [notes, setNotes] = useState(decryptedContent.notes || '');
  const [tags, setTags] = useState(item.tags.join(', '));
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      // Build content object
      const content: DecryptedContent = {};
      if (itemType === 'credential') {
        content.username = username;
        content.password = password;
      } else {
        content.value = value;
      }
      if (notes) content.notes = notes;

      // Encrypt content
      const { encrypted, iv } = await encrypt(content);

      const res = await fetch(`${API_BASE}/vault/items/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          item_type: itemType,
          description: description || null,
          encrypted_data: encrypted,
          iv,
          tags: tags ? tags.split(',').map((t) => t.trim()) : [],
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to update item');
      }

      onUpdated();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update item');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal title="Edit Secret" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Type
            </label>
            <select
              value={itemType}
              onChange={(e) => setItemType(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
            >
              <option value="secret">Secret</option>
              <option value="credential">Credential</option>
              <option value="api_key">API Key</option>
              <option value="certificate">Certificate</option>
              <option value="note">Note</option>
            </select>
          </div>
        </div>

        {itemType === 'credential' ? (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
              />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Value
            </label>
            <textarea
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200 font-mono text-sm"
              rows={3}
            />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
            rows={2}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Tags
            </label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
            />
          </div>
        </div>

        {error && (
          <div className="text-red-400 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-gray-200"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white disabled:opacity-50"
          >
            {isLoading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// Delete Confirm Modal
function DeleteConfirmModal({
  type,
  id,
  onClose,
  onDeleted,
}: {
  type: 'folder' | 'item';
  id: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const endpoint = type === 'folder' ? 'folders' : 'items';
      const res = await fetch(`${API_BASE}/vault/${endpoint}/${id}`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `Failed to delete ${type}`);
      }

      onDeleted();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : `Failed to delete ${type}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal title={`Delete ${type === 'folder' ? 'Folder' : 'Item'}`} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-gray-300">
          Are you sure you want to delete this {type}?{' '}
          {type === 'item' && 'This action cannot be undone.'}
          {type === 'folder' &&
            'Items in this folder will be moved to the root level.'}
        </p>

        {error && (
          <div className="text-red-400 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-gray-200"
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={isLoading}
            className="px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-white disabled:opacity-50"
          >
            {isLoading ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// Modal wrapper component
function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-800 rounded-lg border border-gray-700 w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h3 className="text-lg font-medium text-gray-200">{title}</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-700 rounded"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
