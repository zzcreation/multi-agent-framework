"""
OpenClaw Multi-Tenant Support Module

This module provides multi-tenant isolation and resource management.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class TenantStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass
class TenantQuota:
    """Resource quota for a tenant."""
    max_workers: int = 10
    max_concurrent_tasks: int = 100
    max_storage_mb: int = 1024  # MB
    max_api_calls_per_day: int = 100000
    rate_limit: int = 100  # requests per second


@dataclass
class Tenant:
    """Represents a tenant in the system."""
    tenant_id: str
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    quota: TenantQuota = field(default_factory=TenantQuota)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, str] = field(default_factory=dict)
    
    # Usage tracking
    api_calls_today: int = 0
    active_workers: int = 0
    storage_used_mb: float = 0.0


class TenantManager:
    """Manages tenants and their resources."""
    
    def __init__(self):
        self._tenants: Dict[str, Tenant] = {}
    
    def create_tenant(
        self,
        name: str,
        quota: Optional[TenantQuota] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Tenant:
        """Create a new tenant."""
        tenant_id = str(uuid.uuid4())
        
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            quota=quota or TenantQuota(),
            metadata=metadata or {}
        )
        
        self._tenants[tenant_id] = tenant
        return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by ID."""
        return self._tenants.get(tenant_id)
    
    def list_tenants(self, status: Optional[TenantStatus] = None) -> List[Tenant]:
        """List all tenants, optionally filtered by status."""
        tenants = list(self._tenants.values())
        
        if status:
            tenants = [t for t in tenants if t.status == status]
        
        return tenants
    
    def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        quota: Optional[TenantQuota] = None,
        status: Optional[TenantStatus] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Optional[Tenant]:
        """Update a tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
        
        if name:
            tenant.name = name
        if quota:
            tenant.quota = quota
        if status:
            tenant.status = status
        if metadata:
            tenant.metadata.update(metadata)
        
        tenant.updated_at = datetime.now()
        return tenant
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """Soft delete a tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        
        tenant.status = TenantStatus.DELETED
        tenant.updated_at = datetime.now()
        return True
    
    def suspend_tenant(self, tenant_id: str) -> bool:
        """Suspend a tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        
        tenant.status = TenantStatus.SUSPENDED
        tenant.updated_at = datetime.now()
        return True
    
    def activate_tenant(self, tenant_id: str) -> bool:
        """Activate a suspended tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        
        tenant.status = TenantStatus.ACTIVE
        tenant.updated_at = datetime.now()
        return True
    
    # Resource management
    
    def can_scale_worker(self, tenant_id: str) -> bool:
        """Check if tenant can scale up a worker."""
        tenant = self._tenants.get(tenant_id)
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            return False
        
        return tenant.active_workers < tenant.quota.max_workers
    
    def register_worker(self, tenant_id: str) -> bool:
        """Register a new worker for a tenant."""
        if not self.can_scale_worker(tenant_id):
            return False
        
        tenant = self._tenants.get(tenant_id)
        if tenant:
            tenant.active_workers += 1
            return True
        return False
    
    def unregister_worker(self, tenant_id: str) -> bool:
        """Unregister a worker."""
        tenant = self._tenants.get(tenant_id)
        if not tenant or tenant.active_workers <= 0:
            return False
        
        tenant.active_workers -= 1
        return True
    
    def check_rate_limit(self, tenant_id: str) -> bool:
        """Check if tenant is within rate limit."""
        tenant = self._tenants.get(tenant_id)
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            return False
        
        # Simplified rate limiting check
        # In production, use a proper rate limiter
        return tenant.api_calls_today < tenant.quota.max_api_calls_per_day
    
    def record_api_call(self, tenant_id: str) -> bool:
        """Record an API call for rate limiting."""
        tenant = self._tenants.get(tenant_id)
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            return False
        
        if not self.check_rate_limit(tenant_id):
            return False
        
        tenant.api_calls_today += 1
        return True
    
    def get_tenant_usage(self, tenant_id: str) -> Optional[Dict]:
        """Get tenant resource usage."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
        
        return {
            "tenant_id": tenant.tenant_id,
            "name": tenant.name,
            "status": tenant.status.value,
            "active_workers": tenant.active_workers,
            "max_workers": tenant.quota.max_workers,
            "api_calls_today": tenant.api_calls_today,
            "max_api_calls_per_day": tenant.quota.max_api_calls_per_day,
            "storage_used_mb": tenant.storage_used_mb,
            "max_storage_mb": tenant.quota.max_storage_mb,
        }
    
    def reset_daily_usage(self):
        """Reset daily API call counters (called at midnight)."""
        for tenant in self._tenants.values():
            tenant.api_calls_today = 0


# Global tenant manager instance
_tenant_manager: Optional[TenantManager] = None


def get_tenant_manager() -> TenantManager:
    """Get the global tenant manager instance."""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager