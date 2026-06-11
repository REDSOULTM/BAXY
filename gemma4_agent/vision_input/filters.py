from __future__ import annotations

import math

class OneEuroFilter:
    """
    1 Euro Filter, a speed-based low-pass filter for noisy tracking signals.
    Invented by Casiez et al. to eliminate jitter while minimizing lag.
    """
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        
        self.x_prev: float | None = None
        self.dx_prev = 0.0
        self.t_prev: float | None = None

    def smoothing_factor(self, t_e: float, cutoff: float) -> float:
        r = 2.0 * math.pi * cutoff * t_e
        return r / (r + 1.0)

    def __call__(self, t: float, x: float) -> float:
        """
        Updates the filter with a new sample and returns the smoothed value.
        """
        if self.t_prev is None or self.x_prev is None:
            self.t_prev = t
            self.x_prev = x
            return x

        t_e = t - self.t_prev
        
        # The filter needs a strictly positive time delta.
        # If t_e <= 0 (e.g., duplicated timestamps), we return the previous state.
        if t_e <= 0.0:
            return self.x_prev
            
        # Calculate derivative (velocity)
        dx = (x - self.x_prev) / t_e
        
        # Smooth the derivative to avoid jitter in the cutoff frequency calculation
        edx = self.smoothing_factor(t_e, self.d_cutoff)
        dx_hat = edx * dx + (1.0 - edx) * self.dx_prev
        
        # Calculate dynamic cutoff frequency based on velocity
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        
        # Smooth the signal
        e = self.smoothing_factor(t_e, cutoff)
        x_hat = e * x + (1.0 - e) * self.x_prev
        
        # Update internal state
        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        
        return x_hat

class OneEuroFilter2D:
    """
    A 2D version of the 1 Euro Filter for (X, Y) coordinates.
    """
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0):
        self.filter_x = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self.filter_y = OneEuroFilter(min_cutoff, beta, d_cutoff)
        
    def __call__(self, t: float, x: float, y: float) -> tuple[float, float]:
        return (
            self.filter_x(t, x),
            self.filter_y(t, y)
        )
