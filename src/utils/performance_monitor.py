"""Performance monitoring utilities for PDF outline extraction."""

import time
import psutil
import gc
import logging
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass
from functools import wraps


@dataclass
class ProcessingMetrics:
    """Metrics for processing operations."""
    processing_time: float
    memory_usage_mb: float
    memory_peak_mb: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    rss_mb: float  # Resident Set Size
    vms_mb: float  # Virtual Memory Size
    percent: float
    available_mb: float


class PerformanceMonitor:
    """Monitors and optimizes performance for PDF processing."""
    
    def __init__(self, max_memory_gb: int = 16, max_time_seconds: int = 10):
        """Initialize performance monitor.
        
        Args:
            max_memory_gb: Maximum memory limit in GB
            max_time_seconds: Maximum processing time in seconds
        """
        self.max_memory_bytes = max_memory_gb * 1024 * 1024 * 1024
        self.max_time_seconds = max_time_seconds
        self.logger = logging.getLogger(__name__)
        
    def monitor_processing(self, operation: Callable, *args, **kwargs) -> ProcessingMetrics:
        """Monitor a processing operation.
        
        Args:
            operation: Function to monitor
            *args: Arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            ProcessingMetrics with performance data
        """
        start_time = time.time()
        start_memory = self.get_memory_stats()
        peak_memory = start_memory.rss_mb
        
        try:
            # Monitor memory during execution
            def memory_monitor():
                nonlocal peak_memory
                current_memory = self.get_memory_stats().rss_mb
                peak_memory = max(peak_memory, current_memory)
                
                # Trigger cleanup if memory usage is high
                if current_memory > self.max_memory_bytes * 0.8 / (1024 * 1024):
                    self.trigger_cleanup()
            
            # Execute operation with monitoring
            result = operation(*args, **kwargs)
            memory_monitor()
            
            processing_time = time.time() - start_time
            final_memory = self.get_memory_stats()
            
            # Check performance constraints
            if processing_time > self.max_time_seconds:
                self.logger.warning(f"Processing time exceeded limit: {processing_time:.2f}s > {self.max_time_seconds}s")
            
            if peak_memory > self.max_memory_bytes / (1024 * 1024):
                self.logger.warning(f"Memory usage exceeded limit: {peak_memory:.2f}MB > {self.max_memory_bytes / (1024 * 1024):.2f}MB")
            
            return ProcessingMetrics(
                processing_time=processing_time,
                memory_usage_mb=final_memory.rss_mb,
                memory_peak_mb=peak_memory,
                cpu_percent=psutil.cpu_percent(),
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            final_memory = self.get_memory_stats()
            
            return ProcessingMetrics(
                processing_time=processing_time,
                memory_usage_mb=final_memory.rss_mb,
                memory_peak_mb=peak_memory,
                cpu_percent=psutil.cpu_percent(),
                success=False,
                error_message=str(e)
            )
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory usage statistics.
        
        Returns:
            MemoryStats object with current memory information
        """
        process = psutil.Process()
        memory_info = process.memory_info()
        virtual_memory = psutil.virtual_memory()
        
        return MemoryStats(
            rss_mb=memory_info.rss / (1024 * 1024),
            vms_mb=memory_info.vms / (1024 * 1024),
            percent=process.memory_percent(),
            available_mb=virtual_memory.available / (1024 * 1024)
        )
    
    def check_memory_usage(self) -> bool:
        """Check if memory usage is within limits.
        
        Returns:
            True if memory usage is acceptable
        """
        stats = self.get_memory_stats()
        return stats.rss_mb < (self.max_memory_bytes / (1024 * 1024)) * 0.9
    
    def trigger_cleanup(self) -> None:
        """Trigger memory cleanup operations."""
        self.logger.info("Triggering memory cleanup due to high usage")
        gc.collect()  # Force garbage collection
        
        # Log memory stats after cleanup
        stats = self.get_memory_stats()
        self.logger.info(f"Memory after cleanup: {stats.rss_mb:.2f}MB ({stats.percent:.1f}%)")
    
    def enforce_timeout(self, max_seconds: int) -> Callable:
        """Decorator to enforce timeout on operations.
        
        Args:
            max_seconds: Maximum seconds allowed
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    
                    elapsed = time.time() - start_time
                    if elapsed > max_seconds:
                        self.logger.warning(f"Operation took {elapsed:.2f}s, exceeding {max_seconds}s limit")
                    
                    return result
                    
                except Exception as e:
                    elapsed = time.time() - start_time
                    self.logger.error(f"Operation failed after {elapsed:.2f}s: {str(e)}")
                    raise
            
            return wrapper
        return decorator
    
    def optimize_batch_processing(self, items: list, batch_size: int = 1000) -> list:
        """Optimize batch processing to prevent memory spikes.
        
        Args:
            items: List of items to process
            batch_size: Size of each batch
            
        Returns:
            List of processed items
        """
        processed_items = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # Process batch
            processed_batch = self._process_batch(batch)
            processed_items.extend(processed_batch)
            
            # Monitor and cleanup after each batch
            if not self.check_memory_usage():
                self.trigger_cleanup()
            
            # Log progress
            progress = min(i + batch_size, len(items))
            self.logger.debug(f"Processed {progress}/{len(items)} items")
        
        return processed_items
    
    def _process_batch(self, batch: list) -> list:
        """Process a batch of items (placeholder for actual processing).
        
        Args:
            batch: Batch of items to process
            
        Returns:
            Processed batch
        """
        # This is a placeholder - actual processing would be implemented
        # by the calling code
        return batch
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of current performance metrics.
        
        Returns:
            Dictionary with performance summary
        """
        memory_stats = self.get_memory_stats()
        
        return {
            'memory_usage_mb': memory_stats.rss_mb,
            'memory_percent': memory_stats.percent,
            'memory_available_mb': memory_stats.available_mb,
            'cpu_percent': psutil.cpu_percent(),
            'memory_limit_mb': self.max_memory_bytes / (1024 * 1024),
            'time_limit_seconds': self.max_time_seconds,
            'within_memory_limit': memory_stats.rss_mb < (self.max_memory_bytes / (1024 * 1024)),
        }