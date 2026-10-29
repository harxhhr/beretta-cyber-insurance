"""KYH Collector: receives signed agent reports and turns them into warranty states.

It never prices. Post-bind observations reach the warranty state machine only; the
bound premium is written once at bind and never updated by anything in this package.
"""

__version__ = "2.0.0"
