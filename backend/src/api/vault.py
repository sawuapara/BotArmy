"""API endpoints for secure vault management with server-side encryption."""

import secrets
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db_pool
from ..logging import get_logger
from ..vault import derive_key, encrypt, decrypt, vault_session
from ..vault.persistence import save_last_username, get_last_username

# Argon2 for password hashing
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False
    PasswordHasher = None
    VerifyMismatchError = Exception

logger = get_logger("api.vault")

router = APIRouter(prefix="/vault", tags=["vault"])


# --- Request/Response Models ---

class VaultSetupRequest(BaseModel):
    """Request to set up the vault with a master password."""
    password: str = Field(..., min_length=8, description="Master password (min 8 chars)")


class VaultUnlockRequest(BaseModel):
    """Request to unlock the vault."""
    username: Optional[str] = Field(default=None, description="Username or email")
    password: str = Field(..., description="Master password")
    remember_username: bool = Field(default=False, description="Save username for next login")


class VaultStatusResponse(BaseModel):
    """Response with vault status."""
    is_setup: bool
    created_at: Optional[str] = None


class VaultUnlockResponse(BaseModel):
    """Response after successful unlock."""
    success: bool
    salt: str  # Base64 salt for client-side key derivation


class CreateFolderRequest(BaseModel):
    """Request to create a vault folder."""
    namespace_id: str
    name: str = Field(..., min_length=1, max_length=100)
    parent_folder_id: Optional[str] = None
    description: Optional[str] = None


class UpdateFolderRequest(BaseModel):
    """Request to update a vault folder."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    parent_folder_id: Optional[str] = None


class FolderResponse(BaseModel):
    """Response model for a vault folder."""
    id: str
    namespace_id: str
    parent_folder_id: Optional[str]
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str


class CreateItemRequest(BaseModel):
    """Request to create a vault item."""
    namespace_id: str
    name: str = Field(..., min_length=1, max_length=200)
    item_type: str = Field(default="secret", description="Type: secret, credential, api_key, certificate, note")
    folder_id: Optional[str] = None
    encrypted_data: str = Field(..., description="AES-GCM encrypted JSON blob (base64)")
    iv: str = Field(..., description="Initialization vector (base64)")
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    expires_at: Optional[str] = None


class UpdateItemRequest(BaseModel):
    """Request to update a vault item."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    item_type: Optional[str] = None
    folder_id: Optional[str] = None
    encrypted_data: Optional[str] = None
    iv: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    expires_at: Optional[str] = None


class ItemResponse(BaseModel):
    """Response model for a vault item."""
    id: str
    namespace_id: str
    folder_id: Optional[str]
    name: str
    item_type: str
    encrypted_data: Optional[str]
    iv: Optional[str]
    description: Optional[str]
    tags: list[str]
    created_at: str
    updated_at: str
    expires_at: Optional[str]
    last_accessed_at: Optional[str]


class ItemListResponse(BaseModel):
    """Response model for item list (without encrypted data)."""
    id: str
    namespace_id: str
    folder_id: Optional[str]
    name: str
    item_type: str
    description: Optional[str]
    tags: list[str]
    created_at: str
    updated_at: str
    expires_at: Optional[str]


# --- Vault Setup/Unlock Endpoints ---

@router.get("/last-username")
async def get_last_username_endpoint():
    """Get the last logged-in username for login convenience."""
    username = get_last_username()
    return {"username": username}


@router.get("/status", response_model=VaultStatusResponse)
async def get_vault_status():
    """Check if the vault has been set up (master password configured)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check identity.users for a user with vault configured (password_hash is not null)
        row = await conn.fetchrow("""
            SELECT created_at FROM identity.users
            WHERE password_hash IS NOT NULL
            LIMIT 1
        """)
        if row:
            return VaultStatusResponse(
                is_setup=True,
                created_at=row["created_at"].isoformat()
            )
        return VaultStatusResponse(is_setup=False)


class VaultSetupWithUserRequest(BaseModel):
    """Request to set up the vault with user info and master password."""
    email: str = Field(..., description="User email")
    first_name: str = Field(..., min_length=1, description="First name")
    last_name: str = Field(..., min_length=1, description="Last name")
    password: str = Field(..., min_length=8, description="Master password (min 8 chars)")


@router.post("/setup", response_model=VaultUnlockResponse)
async def setup_vault(request: VaultSetupWithUserRequest):
    """
    Set up the vault with user identity and master password.

    This creates a user in identity.users with:
    - User identity (email, first_name, last_name)
    - Argon2id hash of the password (for verification)
    - Random salt (for client-side PBKDF2 key derivation)

    Only works if no user with vault configured exists.
    """
    if not ARGON2_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Argon2 not available. Install argon2-cffi package."
        )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if vault already set up (any user with password_hash)
        existing = await conn.fetchval("""
            SELECT id FROM identity.users
            WHERE password_hash IS NOT NULL
            LIMIT 1
        """)
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Vault is already set up. Use /vault/unlock to unlock."
            )

        # Generate random salt for client-side key derivation (32 bytes = 256 bits)
        import base64
        salt_bytes = secrets.token_bytes(32)
        salt_b64 = base64.b64encode(salt_bytes).decode('ascii')  # Standard base64 for atob()

        # Hash password with Argon2id
        ph = PasswordHasher()
        password_hash = ph.hash(request.password)

        # Create user with vault credentials
        await conn.execute("""
            INSERT INTO identity.users (email, first_name, last_name, password_hash, salt)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (email) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                password_hash = EXCLUDED.password_hash,
                salt = EXCLUDED.salt
        """, request.email, request.first_name, request.last_name, password_hash, salt_b64)

        logger.info(f"Vault configured for user: {request.email}")

        return VaultUnlockResponse(success=True, salt=salt_b64)


@router.post("/unlock", response_model=VaultUnlockResponse)
async def unlock_vault(request: VaultUnlockRequest):
    """
    Verify the master password and derive encryption key server-side.

    The encryption key is held in memory for the session.
    Use /vault/lock to clear it.
    """
    if not ARGON2_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Argon2 not available. Install argon2-cffi package."
        )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Find user by username/email if provided, otherwise get the only user
        if request.username:
            row = await conn.fetchrow("""
                SELECT id, email, password_hash, salt FROM identity.users
                WHERE (email = $1 OR LOWER(email) = LOWER($1))
                AND password_hash IS NOT NULL
            """, request.username)
            if not row:
                logger.warning(f"Failed login attempt for unknown user: {request.username}")
                raise HTTPException(status_code=401, detail="Invalid credentials")
        else:
            # Backwards compatibility: if no username, get the only user
            row = await conn.fetchrow("""
                SELECT id, email, password_hash, salt FROM identity.users
                WHERE password_hash IS NOT NULL
                LIMIT 1
            """)
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail="Vault not set up. Use /vault/setup first."
                )

        # Verify password
        ph = PasswordHasher()
        try:
            ph.verify(row["password_hash"], request.password)
        except VerifyMismatchError:
            logger.warning(f"Failed login attempt for user: {row['email']}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check if password needs rehash (Argon2 params upgraded)
        if ph.check_needs_rehash(row["password_hash"]):
            new_hash = ph.hash(request.password)
            await conn.execute(
                "UPDATE identity.users SET password_hash = $1 WHERE id = $2",
                new_hash, row["id"]
            )
            logger.info("Rehashed vault password with updated parameters")

        # Derive encryption key and store in memory
        encryption_key = derive_key(request.password, row["salt"])
        vault_session.unlock(encryption_key, str(row["id"]))

        # Update last login
        await conn.execute(
            "UPDATE identity.users SET last_login_at = NOW() WHERE id = $1",
            row["id"]
        )

        # Save username for next login if requested
        if request.remember_username:
            save_last_username(row["email"])

        logger.info(f"Vault unlocked successfully for {row['email']}")

        return VaultUnlockResponse(success=True, salt=row["salt"])


@router.post("/lock")
async def lock_vault():
    """
    Lock the vault by clearing the encryption key from memory.
    """
    if not vault_session.is_unlocked:
        return {"message": "Vault already locked"}

    vault_session.lock()
    logger.info("Vault locked (key cleared from memory)")

    return {"message": "Vault locked"}


@router.get("/session")
async def get_vault_session():
    """
    Get the current vault session status.
    """
    return {
        "is_unlocked": vault_session.is_unlocked,
        "unlocked_at": vault_session.unlocked_at.isoformat() if vault_session.unlocked_at else None,
        "user_id": vault_session.user_id,
    }


class UserResponse(BaseModel):
    """Response model for current user."""
    id: str
    email: str
    first_name: str
    last_name: str


@router.get("/me", response_model=UserResponse)
async def get_current_user():
    """Get the current vault user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, email, first_name, last_name FROM identity.users
            WHERE password_hash IS NOT NULL
            LIMIT 1
        """)
        if not row:
            raise HTTPException(status_code=404, detail="No user found")

        return UserResponse(
            id=str(row["id"]),
            email=row["email"],
            first_name=row["first_name"],
            last_name=row["last_name"],
        )


# --- Folder Endpoints ---

@router.get("/folders", response_model=list[FolderResponse])
async def list_folders(namespace_id: Optional[str] = None):
    """List vault folders, optionally filtered by namespace."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if namespace_id:
            rows = await conn.fetch("""
                SELECT * FROM vault.folders
                WHERE namespace_id = $1
                ORDER BY parent_folder_id NULLS FIRST, name
            """, UUID(namespace_id))
        else:
            rows = await conn.fetch("""
                SELECT * FROM vault.folders
                ORDER BY namespace_id, parent_folder_id NULLS FIRST, name
            """)
        return [_folder_row_to_response(row) for row in rows]


@router.post("/folders", response_model=FolderResponse)
async def create_folder(request: CreateFolderRequest):
    """Create a new vault folder."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        namespace_id = UUID(request.namespace_id)
        parent_folder_id = UUID(request.parent_folder_id) if request.parent_folder_id else None

        # Verify namespace exists
        ns_exists = await conn.fetchval(
            "SELECT id FROM organization.namespaces WHERE id = $1",
            namespace_id
        )
        if not ns_exists:
            raise HTTPException(status_code=404, detail="Namespace not found")

        # Verify parent folder exists and is in same namespace
        if parent_folder_id:
            parent = await conn.fetchrow(
                "SELECT id, namespace_id FROM vault.folders WHERE id = $1",
                parent_folder_id
            )
            if not parent:
                raise HTTPException(status_code=404, detail="Parent folder not found")
            if parent['namespace_id'] != namespace_id:
                raise HTTPException(status_code=400, detail="Parent folder must be in the same namespace")

        # Check for duplicate name in same location
        existing = await conn.fetchval("""
            SELECT id FROM vault.folders
            WHERE namespace_id = $1 AND name = $2 AND parent_folder_id IS NOT DISTINCT FROM $3
        """, namespace_id, request.name, parent_folder_id)
        if existing:
            raise HTTPException(status_code=409, detail="Folder with this name already exists in this location")

        row = await conn.fetchrow("""
            INSERT INTO vault.folders (namespace_id, parent_folder_id, name, description)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """, namespace_id, parent_folder_id, request.name, request.description)

        return _folder_row_to_response(row)


@router.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder(folder_id: UUID):
    """Get a vault folder by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM vault.folders WHERE id = $1",
            folder_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Folder not found")
        return _folder_row_to_response(row)


@router.patch("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(folder_id: UUID, request: UpdateFolderRequest):
    """Update a vault folder."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        current = await conn.fetchrow(
            "SELECT * FROM vault.folders WHERE id = $1",
            folder_id
        )
        if not current:
            raise HTTPException(status_code=404, detail="Folder not found")

        updates = []
        values = []
        param_idx = 1

        if request.name is not None:
            updates.append(f"name = ${param_idx}")
            values.append(request.name)
            param_idx += 1

        if request.description is not None:
            updates.append(f"description = ${param_idx}")
            values.append(request.description)
            param_idx += 1

        if request.parent_folder_id is not None:
            parent_uuid = UUID(request.parent_folder_id) if request.parent_folder_id else None
            if parent_uuid:
                if parent_uuid == folder_id:
                    raise HTTPException(status_code=400, detail="Folder cannot be its own parent")
                parent = await conn.fetchrow(
                    "SELECT id, namespace_id FROM vault.folders WHERE id = $1",
                    parent_uuid
                )
                if not parent:
                    raise HTTPException(status_code=404, detail="Parent folder not found")
                if parent['namespace_id'] != current['namespace_id']:
                    raise HTTPException(status_code=400, detail="Parent folder must be in the same namespace")
            updates.append(f"parent_folder_id = ${param_idx}")
            values.append(parent_uuid)
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(folder_id)
        query = f"""
            UPDATE vault.folders
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(query, *values)
        return _folder_row_to_response(row)


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: UUID):
    """Delete a vault folder. Items in the folder will have their folder_id set to NULL."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check for child folders
        child_count = await conn.fetchval(
            "SELECT COUNT(*) FROM vault.folders WHERE parent_folder_id = $1",
            folder_id
        )
        if child_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete folder with {child_count} child folders. Delete children first."
            )

        deleted = await conn.fetchval(
            "DELETE FROM vault.folders WHERE id = $1 RETURNING id",
            folder_id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Folder not found")
        return {"message": "Folder deleted"}


# --- Item Endpoints ---

@router.get("/items", response_model=list[ItemListResponse])
async def list_items(
    namespace_id: Optional[str] = None,
    folder_id: Optional[str] = None,
    item_type: Optional[str] = None
):
    """
    List vault items (metadata only, no encrypted content).

    Filter by namespace_id, folder_id, or item_type.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        conditions = []
        values = []
        param_idx = 1

        if namespace_id:
            conditions.append(f"namespace_id = ${param_idx}")
            values.append(UUID(namespace_id))
            param_idx += 1

        if folder_id:
            if folder_id == "null":
                conditions.append("folder_id IS NULL")
            else:
                conditions.append(f"folder_id = ${param_idx}")
                values.append(UUID(folder_id))
                param_idx += 1

        if item_type:
            conditions.append(f"item_type = ${param_idx}")
            values.append(item_type)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = await conn.fetch(f"""
            SELECT id, namespace_id, folder_id, name, item_type, description, tags,
                   created_at, updated_at, expires_at
            FROM vault.items
            {where_clause}
            ORDER BY name
        """, *values)

        return [_item_list_row_to_response(row) for row in rows]


@router.post("/items", response_model=ItemResponse)
async def create_item(request: CreateItemRequest):
    """
    Create a new vault item with encrypted content.

    The encrypted_data and iv are generated client-side using AES-GCM.
    The server stores them as-is without decryption.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        namespace_id = UUID(request.namespace_id)
        folder_id = UUID(request.folder_id) if request.folder_id else None
        expires_at = datetime.fromisoformat(request.expires_at) if request.expires_at else None

        # Verify namespace exists
        ns_exists = await conn.fetchval(
            "SELECT id FROM organization.namespaces WHERE id = $1",
            namespace_id
        )
        if not ns_exists:
            raise HTTPException(status_code=404, detail="Namespace not found")

        # Verify folder exists if specified
        if folder_id:
            folder = await conn.fetchrow(
                "SELECT id, namespace_id FROM vault.folders WHERE id = $1",
                folder_id
            )
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")
            if folder['namespace_id'] != namespace_id:
                raise HTTPException(status_code=400, detail="Folder must be in the same namespace")

        # Check for duplicate name in same location
        existing = await conn.fetchval("""
            SELECT id FROM vault.items
            WHERE namespace_id = $1 AND name = $2 AND folder_id IS NOT DISTINCT FROM $3
        """, namespace_id, request.name, folder_id)
        if existing:
            raise HTTPException(status_code=409, detail="Item with this name already exists in this location")

        row = await conn.fetchrow("""
            INSERT INTO vault.items
            (namespace_id, folder_id, name, item_type, encrypted_data, iv, description, tags, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
        """, namespace_id, folder_id, request.name, request.item_type,
            request.encrypted_data, request.iv, request.description,
            request.tags, expires_at)

        return _item_row_to_response(row)


@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: UUID):
    """
    Get a vault item by ID, including encrypted content.

    Updates last_accessed_at timestamp.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE vault.items
            SET last_accessed_at = NOW()
            WHERE id = $1
            RETURNING *
        """, item_id)

        if not row:
            raise HTTPException(status_code=404, detail="Item not found")

        return _item_row_to_response(row)


@router.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item(item_id: UUID, request: UpdateItemRequest):
    """Update a vault item."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        current = await conn.fetchrow(
            "SELECT * FROM vault.items WHERE id = $1",
            item_id
        )
        if not current:
            raise HTTPException(status_code=404, detail="Item not found")

        updates = []
        values = []
        param_idx = 1

        if request.name is not None:
            updates.append(f"name = ${param_idx}")
            values.append(request.name)
            param_idx += 1

        if request.item_type is not None:
            updates.append(f"item_type = ${param_idx}")
            values.append(request.item_type)
            param_idx += 1

        if request.folder_id is not None:
            folder_uuid = UUID(request.folder_id) if request.folder_id else None
            if folder_uuid:
                folder = await conn.fetchrow(
                    "SELECT id, namespace_id FROM vault.folders WHERE id = $1",
                    folder_uuid
                )
                if not folder:
                    raise HTTPException(status_code=404, detail="Folder not found")
                if folder['namespace_id'] != current['namespace_id']:
                    raise HTTPException(status_code=400, detail="Folder must be in the same namespace")
            updates.append(f"folder_id = ${param_idx}")
            values.append(folder_uuid)
            param_idx += 1

        if request.encrypted_data is not None:
            updates.append(f"encrypted_data = ${param_idx}")
            values.append(request.encrypted_data)
            param_idx += 1

        if request.iv is not None:
            updates.append(f"iv = ${param_idx}")
            values.append(request.iv)
            param_idx += 1

        if request.description is not None:
            updates.append(f"description = ${param_idx}")
            values.append(request.description)
            param_idx += 1

        if request.tags is not None:
            updates.append(f"tags = ${param_idx}")
            values.append(request.tags)
            param_idx += 1

        if request.expires_at is not None:
            expires_at = datetime.fromisoformat(request.expires_at) if request.expires_at else None
            updates.append(f"expires_at = ${param_idx}")
            values.append(expires_at)
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(item_id)
        query = f"""
            UPDATE vault.items
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(query, *values)
        return _item_row_to_response(row)


@router.delete("/items/{item_id}")
async def delete_item(item_id: UUID):
    """Delete a vault item."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            "DELETE FROM vault.items WHERE id = $1 RETURNING id",
            item_id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"message": "Item deleted"}


# --- Server-Side Encryption Endpoints ---

class QuickAddRequest(BaseModel):
    """Request to add an item with plaintext (server encrypts)."""
    namespace_id: str
    name: str = Field(..., min_length=1, max_length=200)
    secret: str = Field(..., description="Plaintext secret to encrypt")
    item_type: str = Field(default="api_key", description="Type: secret, credential, api_key, certificate, note")
    folder_id: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class DecryptedItemResponse(BaseModel):
    """Response with decrypted item content."""
    id: str
    namespace_id: str
    folder_id: Optional[str]
    name: str
    item_type: str
    secret: str  # Decrypted content
    description: Optional[str]
    tags: list[str]
    created_at: str
    updated_at: str


@router.post("/items/quick-add", response_model=ItemResponse)
async def quick_add_item(request: QuickAddRequest):
    """
    Add a vault item with plaintext - server encrypts it.

    Requires vault to be unlocked (key in memory).
    This is for programmatic access - the server encrypts the secret
    before storing it.
    """
    if not vault_session.is_unlocked:
        raise HTTPException(
            status_code=401,
            detail="Vault is locked. Unlock first with /vault/unlock"
        )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        namespace_id = UUID(request.namespace_id)
        folder_id = UUID(request.folder_id) if request.folder_id else None

        # Verify namespace exists
        ns_exists = await conn.fetchval(
            "SELECT id FROM organization.namespaces WHERE id = $1",
            namespace_id
        )
        if not ns_exists:
            raise HTTPException(status_code=404, detail="Namespace not found")

        # Verify folder exists if specified
        if folder_id:
            folder = await conn.fetchrow(
                "SELECT id, namespace_id FROM vault.folders WHERE id = $1",
                folder_id
            )
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")
            if folder['namespace_id'] != namespace_id:
                raise HTTPException(status_code=400, detail="Folder must be in the same namespace")

        # Check for duplicate name in same location
        existing = await conn.fetchval("""
            SELECT id FROM vault.items
            WHERE namespace_id = $1 AND name = $2 AND folder_id IS NOT DISTINCT FROM $3
        """, namespace_id, request.name, folder_id)
        if existing:
            raise HTTPException(status_code=409, detail="Item with this name already exists in this location")

        # Encrypt the secret server-side
        encrypted_data, iv = encrypt(vault_session.key, request.secret)

        row = await conn.fetchrow("""
            INSERT INTO vault.items
            (namespace_id, folder_id, name, item_type, encrypted_data, iv, description, tags)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
        """, namespace_id, folder_id, request.name, request.item_type,
            encrypted_data, iv, request.description, request.tags)

        logger.info(f"Quick-added vault item: {request.name}")

        return _item_row_to_response(row)


@router.get("/items/{item_id}/decrypted", response_model=DecryptedItemResponse)
async def get_item_decrypted(item_id: UUID):
    """
    Get a vault item with decrypted content.

    Requires vault to be unlocked (key in memory).
    """
    if not vault_session.is_unlocked:
        raise HTTPException(
            status_code=401,
            detail="Vault is locked. Unlock first with /vault/unlock"
        )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE vault.items
            SET last_accessed_at = NOW()
            WHERE id = $1
            RETURNING *
        """, item_id)

        if not row:
            raise HTTPException(status_code=404, detail="Item not found")

        # Decrypt the secret
        try:
            decrypted = decrypt(vault_session.key, row["encrypted_data"], row["iv"])
        except Exception as e:
            logger.error(f"Failed to decrypt item {item_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt item")

        return {
            "id": str(row["id"]),
            "namespace_id": str(row["namespace_id"]),
            "folder_id": str(row["folder_id"]) if row["folder_id"] else None,
            "name": row["name"],
            "item_type": row["item_type"],
            "secret": decrypted,
            "description": row["description"],
            "tags": row["tags"] or [],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }


@router.get("/secrets/{name}")
async def get_secret_by_name(name: str, namespace_id: Optional[str] = None):
    """
    Get a decrypted secret by name (convenience endpoint).

    Useful for backend services to fetch API keys, etc.
    Requires vault to be unlocked.
    """
    if not vault_session.is_unlocked:
        raise HTTPException(
            status_code=401,
            detail="Vault is locked. Unlock first with /vault/unlock"
        )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if namespace_id:
            row = await conn.fetchrow("""
                SELECT * FROM vault.items
                WHERE name = $1 AND namespace_id = $2
            """, name, UUID(namespace_id))
        else:
            # Get first match across all namespaces
            row = await conn.fetchrow("""
                SELECT * FROM vault.items
                WHERE name = $1
                ORDER BY created_at
                LIMIT 1
            """, name)

        if not row:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")

        # Decrypt
        try:
            decrypted = decrypt(vault_session.key, row["encrypted_data"], row["iv"])
        except Exception as e:
            logger.error(f"Failed to decrypt secret {name}: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt secret")

        # Update last accessed
        await conn.execute(
            "UPDATE vault.items SET last_accessed_at = NOW() WHERE id = $1",
            row["id"]
        )

        return {"name": name, "secret": decrypted}


# --- Helper Functions ---

def _folder_row_to_response(row) -> dict:
    """Convert a database row to folder response dict."""
    return {
        "id": str(row["id"]),
        "namespace_id": str(row["namespace_id"]),
        "parent_folder_id": str(row["parent_folder_id"]) if row["parent_folder_id"] else None,
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def _item_row_to_response(row) -> dict:
    """Convert a database row to item response dict."""
    return {
        "id": str(row["id"]),
        "namespace_id": str(row["namespace_id"]),
        "folder_id": str(row["folder_id"]) if row["folder_id"] else None,
        "name": row["name"],
        "item_type": row["item_type"],
        "encrypted_data": row["encrypted_data"],
        "iv": row["iv"],
        "description": row["description"],
        "tags": row["tags"] or [],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
        "last_accessed_at": row["last_accessed_at"].isoformat() if row["last_accessed_at"] else None,
    }


def _item_list_row_to_response(row) -> dict:
    """Convert a database row to item list response dict (no encrypted content)."""
    return {
        "id": str(row["id"]),
        "namespace_id": str(row["namespace_id"]),
        "folder_id": str(row["folder_id"]) if row["folder_id"] else None,
        "name": row["name"],
        "item_type": row["item_type"],
        "description": row["description"],
        "tags": row["tags"] or [],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
    }
