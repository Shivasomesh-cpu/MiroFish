"""
Cost Tracker Service

Provides LLM cost estimation before simulation and tracking during runtime.
Includes rate limiting to prevent API quota exhaustion.

Features:
- Pre-simulation cost estimates (low/high range)
- Running token counter per simulation
- MAX_TOKENS_PER_RUN limit with pause on exceed
- Token bucket rate limiter for API calls
"""

import json
import os
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('posiedon.cost_tracker')


# Default pricing file path
PRICING_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'pricing.json')


@dataclass
class PricingInfo:
    """Pricing information for a model."""
    input_price_per_1k: float
    output_price_per_1k: float
    context_window: int
    description: str = ""


@dataclass
class CostEstimate:
    """Cost estimate for a simulation run."""
    num_agents: int
    num_rounds: int
    model_name: str
    
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    
    low_cost_usd: float
    high_cost_usd: float
    average_cost_usd: float
    
    estimation_variance: float = 0.3  # +/- 30% by default
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_agents": self.num_agents,
            "num_rounds": self.num_rounds,
            "model_name": self.model_name,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
            "low_cost_usd": round(self.low_cost_usd, 4),
            "high_cost_usd": round(self.high_cost_usd, 4),
            "average_cost_usd": round(self.average_cost_usd, 4),
            "estimation_variance": self.estimation_variance,
        }


@dataclass
class TokenUsage:
    """Token usage tracking for a simulation."""
    simulation_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    request_count: int = 0
    started_at: Optional[str] = None
    last_updated: Optional[str] = None
    limit_exceeded: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "request_count": self.request_count,
            "started_at": self.started_at,
            "last_updated": self.last_updated,
            "limit_exceeded": self.limit_exceeded,
        }


class TokenBucket:
    """
    Token bucket rate limiter.
    
    Allows bursts up to bucket capacity, then refills at a steady rate.
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now
    
    def acquire(self, tokens: int = 1, timeout: float = 60.0) -> bool:
        """
        Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait for tokens
        
        Returns:
            True if tokens acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return False
            
            # Calculate wait time for tokens to become available
            with self._lock:
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_rate
                wait_time = min(wait_time, timeout - elapsed, 1.0)  # Cap at 1 second
            
            time.sleep(wait_time)
        
        return False


class CostTracker:
    """
    Tracks LLM costs and enforces rate limits.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._pricing: Dict[str, PricingInfo] = {}
        self._estimation_defaults: Dict[str, float] = {}
        self._rate_limits: Dict[str, Dict[str, int]] = {}
        self._token_usage: Dict[str, TokenUsage] = {}
        self._rate_limiters: Dict[str, TokenBucket] = {}
        
        self._load_pricing()
    
    def _load_pricing(self):
        """Load pricing information from pricing.json."""
        pricing_path = PRICING_FILE
        if not os.path.exists(pricing_path):
            pricing_path = os.path.join(os.path.dirname(__file__), '..', '..', 'pricing.json')
        
        try:
            with open(pricing_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load model pricing
            for model_name, pricing in data.get('models', {}).items():
                self._pricing[model_name] = PricingInfo(
                    input_price_per_1k=pricing.get('input_price_per_1k', 0.001),
                    output_price_per_1k=pricing.get('output_price_per_1k', 0.002),
                    context_window=pricing.get('context_window', 8000),
                    description=pricing.get('description', '')
                )
            
            # Load estimation defaults
            self._estimation_defaults = data.get('estimation_defaults', {
                'avg_input_tokens_per_action': 1500,
                'avg_output_tokens_per_action': 500,
                'avg_actions_per_agent_per_round': 2.5,
                'estimation_variance': 0.3
            })
            
            # Load rate limits
            self._rate_limits = data.get('rate_limits', {})
            
            logger.info(f"Loaded pricing for {len(self._pricing)} models")
            
        except Exception as e:
            logger.warning(f"Failed to load pricing.json: {e}, using defaults")
            self._pricing['default'] = PricingInfo(
                input_price_per_1k=0.001,
                output_price_per_1k=0.002,
                context_window=8000
            )
    
    def get_pricing(self, model_name: str) -> PricingInfo:
        """Get pricing info for a model."""
        # Try exact match
        if model_name in self._pricing:
            return self._pricing[model_name]
        
        # Try partial match (e.g., "gpt-4o" matches "gpt-4o-mini")
        for name, pricing in self._pricing.items():
            if name in model_name or model_name in name:
                return pricing
        
        # Return default
        return self._pricing.get('default', PricingInfo(0.001, 0.002, 8000))
    
    def estimate_cost(
        self,
        num_agents: int,
        num_rounds: int,
        model_name: Optional[str] = None,
        avg_actions_per_agent_per_round: Optional[float] = None
    ) -> CostEstimate:
        """
        Estimate the cost of running a simulation.
        
        Args:
            num_agents: Number of agents in simulation
            num_rounds: Number of rounds to run
            model_name: LLM model name (uses config default if not specified)
            avg_actions_per_agent_per_round: Override default actions per agent
        
        Returns:
            CostEstimate with low/high range
        """
        model_name = model_name or Config.LLM_MODEL_NAME or "default"
        pricing = self.get_pricing(model_name)
        
        # Get estimation parameters
        avg_input = self._estimation_defaults.get('avg_input_tokens_per_action', 1500)
        avg_output = self._estimation_defaults.get('avg_output_tokens_per_action', 500)
        avg_actions = avg_actions_per_agent_per_round or self._estimation_defaults.get('avg_actions_per_agent_per_round', 2.5)
        variance = self._estimation_defaults.get('estimation_variance', 0.3)
        
        # Calculate total expected tokens
        total_actions = num_agents * num_rounds * avg_actions
        estimated_input = int(total_actions * avg_input)
        estimated_output = int(total_actions * avg_output)
        estimated_total = estimated_input + estimated_output
        
        # Calculate costs
        input_cost = (estimated_input / 1000) * pricing.input_price_per_1k
        output_cost = (estimated_output / 1000) * pricing.output_price_per_1k
        avg_cost = input_cost + output_cost
        
        low_cost = avg_cost * (1 - variance)
        high_cost = avg_cost * (1 + variance)
        
        return CostEstimate(
            num_agents=num_agents,
            num_rounds=num_rounds,
            model_name=model_name,
            estimated_input_tokens=estimated_input,
            estimated_output_tokens=estimated_output,
            estimated_total_tokens=estimated_total,
            low_cost_usd=low_cost,
            high_cost_usd=high_cost,
            average_cost_usd=avg_cost,
            estimation_variance=variance
        )
    
    def start_tracking(self, simulation_id: str) -> TokenUsage:
        """Start tracking token usage for a simulation."""
        usage = TokenUsage(
            simulation_id=simulation_id,
            started_at=datetime.now().isoformat()
        )
        self._token_usage[simulation_id] = usage
        logger.info(f"Started cost tracking for simulation {simulation_id}")
        return usage
    
    def record_usage(
        self,
        simulation_id: str,
        input_tokens: int,
        output_tokens: int,
        model_name: Optional[str] = None
    ) -> Tuple[TokenUsage, bool]:
        """
        Record token usage from an LLM call.
        
        Args:
            simulation_id: Simulation ID
            input_tokens: Input tokens used
            output_tokens: Output tokens generated
            model_name: Model used (for pricing)
        
        Returns:
            Tuple of (updated TokenUsage, whether limit exceeded)
        """
        if simulation_id not in self._token_usage:
            self.start_tracking(simulation_id)
        
        usage = self._token_usage[simulation_id]
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        usage.total_tokens += input_tokens + output_tokens
        usage.request_count += 1
        usage.last_updated = datetime.now().isoformat()
        
        # Update cost estimate
        model_name = model_name or Config.LLM_MODEL_NAME or "default"
        pricing = self.get_pricing(model_name)
        usage.estimated_cost_usd = (
            (usage.input_tokens / 1000) * pricing.input_price_per_1k +
            (usage.output_tokens / 1000) * pricing.output_price_per_1k
        )
        
        # Check token limit
        max_tokens = int(os.environ.get('MAX_TOKENS_PER_RUN', 0))
        if max_tokens > 0 and usage.total_tokens >= max_tokens:
            usage.limit_exceeded = True
            logger.warning(f"Token limit exceeded for {simulation_id}: {usage.total_tokens} >= {max_tokens}")
            return usage, True
        
        return usage, False
    
    def get_usage(self, simulation_id: str) -> Optional[TokenUsage]:
        """Get current token usage for a simulation."""
        return self._token_usage.get(simulation_id)
    
    def get_summary(self, simulation_id: str) -> Dict[str, Any]:
        """Get usage summary for a simulation."""
        usage = self._token_usage.get(simulation_id)
        if not usage:
            return {
                "simulation_id": simulation_id,
                "status": "not_tracked",
                "message": "No usage tracking found for this simulation"
            }
        
        return {
            "simulation_id": simulation_id,
            "status": "tracked",
            "usage": usage.to_dict()
        }
    
    def stop_tracking(self, simulation_id: str) -> Optional[TokenUsage]:
        """Stop tracking and return final usage."""
        usage = self._token_usage.pop(simulation_id, None)
        if usage:
            logger.info(f"Stopped cost tracking for {simulation_id}: {usage.total_tokens} tokens, ${usage.estimated_cost_usd:.4f}")
        return usage
    
    def get_rate_limiter(self, provider: str = "default") -> TokenBucket:
        """Get or create a rate limiter for an API provider."""
        if provider not in self._rate_limiters:
            limits = self._rate_limits.get(provider, self._rate_limits.get('default', {
                'requests_per_minute': 100,
                'tokens_per_minute': 50000
            }))
            
            # Create bucket with requests per second capacity
            requests_per_minute = limits.get('requests_per_minute', 100)
            capacity = requests_per_minute
            refill_rate = requests_per_minute / 60.0  # Per second
            
            self._rate_limiters[provider] = TokenBucket(capacity, refill_rate)
            logger.debug(f"Created rate limiter for {provider}: {requests_per_minute} req/min")
        
        return self._rate_limiters[provider]
    
    def wait_for_rate_limit(self, provider: str = "default", timeout: float = 60.0) -> bool:
        """
        Wait for rate limit token if needed.
        
        Args:
            provider: API provider name
            timeout: Maximum time to wait
        
        Returns:
            True if can proceed, False if timeout
        """
        limiter = self.get_rate_limiter(provider)
        return limiter.acquire(1, timeout)


# Global instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


def estimate_simulation_cost(
    num_agents: int,
    num_rounds: int,
    model_name: Optional[str] = None
) -> CostEstimate:
    """
    Convenience function to estimate simulation cost.
    
    Args:
        num_agents: Number of agents
        num_rounds: Number of rounds
        model_name: LLM model name
    
    Returns:
        CostEstimate with low/high range
    """
    return get_cost_tracker().estimate_cost(num_agents, num_rounds, model_name)
