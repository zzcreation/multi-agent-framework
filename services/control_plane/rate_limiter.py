"""
Rate Limiting and Circuit Breaker Implementation

This module provides:
1. Token Bucket rate limiter
2. Sliding Window rate limiter
3. Circuit Breaker pattern
"""

from __future__ import annotations

import time
import threading
from typing import Dict, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for Circuit Breaker"""
    failure_threshold: int = 5          # Failures before opening circuit
    success_threshold: int = 3          # Successes to close circuit
    timeout_seconds: float = 30.0       # Time before trying half-open
    half_open_max_calls: int = 3       # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit Breaker implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject all requests
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()
    
    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._last_failure_time and \
                   time.time() - self._last_failure_time > self.config.timeout_seconds:
                    logger.info(f"Circuit breaker '{self.name}': Opening to HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state
    
    def can_execute(self) -> bool:
        """Check if a request can be executed"""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            return False
        elif state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.config.half_open_max_calls
        return False
    
    def record_success(self) -> None:
        """Record a successful execution"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls += 1
                if self._success_count >= self.config.success_threshold:
                    logger.info(f"Circuit breaker '{self.name}': Closing circuit")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed execution"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit breaker '{self.name}': Opening circuit after half-open failure")
                self._state = CircuitState.OPEN
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    logger.warning(f"Circuit breaker '{self.name}': Opening circuit after {self._failure_count} failures")
                    self._state = CircuitState.OPEN
    
    def execute(self, func: Callable[[], Any], fallback: Optional[Callable[[], Any]] = None) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            fallback: Optional fallback function if circuit is open
            
        Returns:
            Result of func or fallback
            
        Raises:
            Exception: If circuit is open and no fallback provided
        """
        if not self.can_execute():
            if fallback:
                return fallback()
            raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            if fallback:
                return fallback()
            raise


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class TokenBucketRateLimiter:
    """
    Token Bucket rate limiter.
    
    Allows burst up to bucket_size, then refills at rate per second.
    """
    
    def __init__(self, rate: float, bucket_size: int):
        """
        Args:
            rate: Tokens added per second
            bucket_size: Maximum bucket size (burst capacity)
        """
        self.rate = rate
        self.bucket_size = bucket_size
        self._tokens = float(bucket_size)
        self._last_refill = time.time()
        self._lock = threading.Lock()
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self.bucket_size, self._tokens + elapsed * self.rate)
        self._last_refill = now
    
    def acquire(self, tokens: int = 1, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Try to acquire tokens.
        
        Args:
            tokens: Number of tokens to acquire
            block: Whether to block until tokens available
            timeout: Max seconds to wait (None = wait forever)
            
        Returns:
            True if tokens acquired, False otherwise
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                self._refill()
                
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
            
            if not block:
                return False
            
            if timeout is not None and (time.time() - start_time) >= timeout:
                return False
            
            # Wait a bit before retrying
            time.sleep(0.01)
    
    def get_available_tokens(self) -> float:
        """Get current available tokens"""
        with self._lock:
            self._refill()
            return self._tokens


class SlidingWindowRateLimiter:
    """
    Sliding Window rate limiter.
    
    More accurate than token bucket, tracks requests in sliding time window.
    """
    
    def __init__(self, max_requests: int, window_seconds: float):
        """
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: deque = deque()
        self._lock = threading.Lock()
    
    def _cleanup_old_requests(self) -> None:
        """Remove requests outside the window"""
        now = time.time()
        cutoff = now - self.window_seconds
        
        while self._requests and self._requests[0] < cutoff:
            self._requests.popleft()
    
    def acquire(self, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Try to acquire a request slot.
        
        Args:
            block: Whether to block until slot available
            timeout: Max seconds to wait
            
        Returns:
            True if slot acquired, False otherwise
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                self._cleanup_old_requests()
                
                if len(self._requests) < self.max_requests:
                    self._requests.append(time.time())
                    return True
            
            if not block:
                return False
            
            if timeout is not None and (time.time() - start_time) >= timeout:
                return False
            
            time.sleep(0.01)
    
    def get_current_count(self) -> int:
        """Get current request count in window"""
        with self._lock:
            self._cleanup_old_requests()
            return len(self._requests)


class RateLimiterRegistry:
    """
    Registry for managing multiple rate limiters.
    
    Supports different limiters for different resources/tenants.
    """
    
    def __init__(self):
        self._limiters: Dict[str, TokenBucketRateLimiter] = {}
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get_or_create_limiter(
        self, 
        key: str, 
        rate: float, 
        bucket_size: int
    ) -> TokenBucketRateLimiter:
        """Get existing limiter or create new one"""
        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = TokenBucketRateLimiter(rate, bucket_size)
            return self._limiters[key]
    
    def get_or_create_breaker(
        self,
        key: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one"""
        with self._lock:
            if key not in self._breakers:
                self._breakers[key] = CircuitBreaker(key, config)
            return self._breakers[key]
    
    def check_rate_limit(self, key: str, rate: float, bucket_size: int) -> bool:
        """Check if request is allowed under rate limit"""
        limiter = self.get_or_create_limiter(key, rate, bucket_size)
        return limiter.acquire()
    
    def get_circuit_breaker(self, key: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by key"""
        with self._lock:
            return self._breakers.get(key)
    
    def get_all_stats(self) -> Dict:
        """Get statistics for all limiters and breakers"""
        stats = {
            "limiters": {},
            "breakers": {}
        }
        
        with self._lock:
            for key, limiter in self._limiters.items():
                stats["limiters"][key] = {
                    "available_tokens": limiter.get_available_tokens(),
                    "rate": limiter.rate,
                    "bucket_size": limiter.bucket_size
                }
            
            for key, breaker in self._breakers.items():
                stats["breakers"][key] = {
                    "state": breaker.state.value,
                    "failure_count": breaker._failure_count,
                    "success_count": breaker._success_count
                }
        
        return stats


# Global instance
_rate_limiter_registry: Optional[RateLimiterRegistry] = None


def get_rate_limiter_registry() -> RateLimiterRegistry:
    """Get global rate limiter registry instance"""
    global _rate_limiter_registry
    if _rate_limiter_registry is None:
        _rate_limiter_registry = RateLimiterRegistry()
    return _rate_limiter_registry