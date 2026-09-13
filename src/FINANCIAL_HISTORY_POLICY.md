# Financial history policy

Use the maximum reliable history available from the provider, up to 10 years. Never require 10 years to calculate a metric.

- Missing observations remain missing; never substitute zero.
- CAGR requires at least 2 valid observations.
- Trend and consistency calculations require at least 3 valid observations.
- Each metric uses its own valid observations; one metric's missing years must not invalidate another metric.
- If a metric does not meet its minimum observations, return `None`/unavailable rather than fabricate a result.
