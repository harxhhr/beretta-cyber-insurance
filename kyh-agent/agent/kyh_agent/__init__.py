"""KYH Live Monitoring Agent.

A read-only endpoint posture sensor for the KYH Cyber Insurance platform.
It observes whether the security controls warranted at policy bind are still
in place on a machine, and reports signed, timestamped results to the KYH
collector. It never changes system state and never accepts commands.
"""

__version__ = "2.0.0"
SCHEMA_VERSION = 2
